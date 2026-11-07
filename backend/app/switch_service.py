import os
import asyncio
import httpx
from typing import List, Dict, Any, Optional

SWITCH_MATTERMOST_URL = os.getenv("SWITCH_MATTERMOST_URL", "http://localhost:49375").rstrip("/")
SWITCH_BOT_TOKEN = os.getenv("SWITCH_BOT_TOKEN", "utw9s444tff18d4yqit4hrzk9e")
SWITCH_CHANNEL_ID = os.getenv("SWITCH_CHANNEL_ID", "bk7165is4bb6ugqtr3fcer1hur")
SWITCH_ROOM_NAME = os.getenv("SWITCH_ROOM_NAME", "lifeos-planning")
SWITCH_NOVA_HANDLE = os.getenv("SWITCH_NOVA_HANDLE", "@nova-anant")

# Configurable timeouts & retries via env
SWITCH_REQUEST_TIMEOUT = float(os.getenv("SWITCH_REQUEST_TIMEOUT", "10.0"))
SWITCH_POLL_TIMEOUT = float(os.getenv("SWITCH_POLL_TIMEOUT", "45.0"))
SWITCH_POLL_INTERVAL = float(os.getenv("SWITCH_POLL_INTERVAL", "2.0"))
SWITCH_MAX_RETRIES = int(os.getenv("SWITCH_MAX_RETRIES", "2"))

KNOWN_AGENTS = ["nova", "scholar", "builder", "planner", "guardian"]
DOCKER_RESTART_INSTRUCTIONS = (
    "Switch or Mattermost is unreachable. To restore:\n"
    "1. Check if Docker is running (`docker ps`).\n"
    "2. If Mattermost container stopped, launch Switch Console app or run `docker compose -f mattermost-compose.yml up -d`.\n"
    "3. Ensure Switch Core service is running (`python -m switch_core.main`)."
)


class SwitchClient:
    def __init__(self, base_url: str = SWITCH_MATTERMOST_URL, token: str = SWITCH_BOT_TOKEN):
        self.base_url = base_url
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        max_retries: int = SWITCH_MAX_RETRIES,
        timeout: float = SWITCH_REQUEST_TIMEOUT,
        **kwargs
    ) -> httpx.Response:
        """Execute HTTP request with configurable retries and exponential backoff."""
        url = f"{self.base_url}{endpoint}"
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.request(method, url, headers=self.headers, **kwargs)
                    # Retry on 502/503/504 Bad Gateway / Service Unavailable
                    if resp.status_code in (502, 503, 504) and attempt < max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
                        continue
                    return resp
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
                last_error = exc
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))
                    continue
        raise last_error or RuntimeError(f"Request failed to {url}")

    async def health_check(self) -> Dict[str, Any]:
        """Check if local Switch and Mattermost services are reachable and responsive."""
        result = {
            "switch_available": False,
            "mattermost_available": False,
            "channel_accessible": False,
            "agents_configured": KNOWN_AGENTS,
            "error_message": None,
            "restart_instructions": None,
        }

        try:
            ping_res = await self._request_with_retry(
                "GET", "/api/v4/system/ping", max_retries=1, timeout=3.0
            )
            if ping_res.status_code == 200 and ping_res.json().get("status") == "OK":
                result["mattermost_available"] = True
                result["switch_available"] = True
            else:
                result["error_message"] = f"Mattermost ping returned status {ping_res.status_code}"
                result["restart_instructions"] = DOCKER_RESTART_INSTRUCTIONS
                return result
        except Exception as e:
            result["error_message"] = f"Cannot reach Switch/Mattermost on {self.base_url}: {str(e)}"
            result["restart_instructions"] = DOCKER_RESTART_INSTRUCTIONS
            return result

        # Check channel access
        try:
            channel_id = await self.get_channel_id()
            chan_res = await self._request_with_retry(
                "GET", f"/api/v4/channels/{channel_id}", max_retries=1, timeout=3.0
            )
            if chan_res.status_code == 200:
                result["channel_accessible"] = True
            else:
                result["error_message"] = f"Channel access failed with status {chan_res.status_code}"
                result["restart_instructions"] = DOCKER_RESTART_INSTRUCTIONS
        except Exception as e:
            result["error_message"] = f"Failed to access room channel: {str(e)}"
            result["restart_instructions"] = DOCKER_RESTART_INSTRUCTIONS

        return result

    async def get_channel_id(self, channel_name: str = SWITCH_ROOM_NAME) -> str:
        """Returns the channel ID for the room or fallback to SWITCH_CHANNEL_ID."""
        if SWITCH_CHANNEL_ID:
            return SWITCH_CHANNEL_ID
        try:
            res = await self._request_with_retry("GET", f"/api/v4/channels/name/{channel_name}")
            if res.status_code == 200:
                return res.json().get("id", SWITCH_CHANNEL_ID)
        except Exception:
            pass
        return SWITCH_CHANNEL_ID

    async def send_planning_request(self, message: str, channel_id: Optional[str] = None) -> Dict[str, Any]:
        """Post a user planning message to Nova in the Switch room."""
        target_channel = channel_id or await self.get_channel_id()
        formatted_message = message if SWITCH_NOVA_HANDLE in message else f"{SWITCH_NOVA_HANDLE}\n\n{message}"

        res = await self._request_with_retry(
            "POST",
            "/api/v4/posts",
            json={
                "channel_id": target_channel,
                "message": formatted_message,
            },
        )
        if res.status_code != 201:
            raise RuntimeError(f"Failed to post to Switch room: {res.status_code} {res.text}")
        return res.json()

    async def fetch_recent_messages(self, channel_id: Optional[str] = None, limit: int = 40) -> List[Dict[str, Any]]:
        """Fetch real posts from the room concurrently mapped with user metadata."""
        target_channel = channel_id or await self.get_channel_id()

        # Concurrent fetch for posts and users
        posts_task = self._request_with_retry(
            "GET",
            f"/api/v4/channels/{target_channel}/posts",
            params={"per_page": limit},
        )
        users_task = self._request_with_retry(
            "GET",
            "/api/v4/users",
            params={"per_page": 50},
        )

        posts_res, users_res = await asyncio.gather(posts_task, users_task, return_exceptions=True)

        if isinstance(posts_res, Exception):
            raise posts_res
        if posts_res.status_code != 200:
            raise RuntimeError(f"Failed to fetch posts from Switch: {posts_res.status_code} {posts_res.text}")

        user_map = {}
        if not isinstance(users_res, Exception) and users_res.status_code == 200:
            for u in users_res.json():
                user_map[u["id"]] = u["username"]

        data = posts_res.json()
        order = data.get("order", [])
        posts_dict = data.get("posts", {})

        formatted = []
        for post_id in order:
            p = posts_dict.get(post_id, {})
            msg = p.get("message", "").strip()
            # Exclude internal temporary tool execution indicators
            if msg.startswith("**Working…") or msg.startswith("**Worked for") or msg.startswith("**Queued"):
                continue
            uid = p.get("user_id")
            uname = user_map.get(uid, "agent")
            formatted.append({
                "id": p.get("id"),
                "user_id": uid,
                "username": uname,
                "message": msg,
                "root_id": p.get("root_id"),
                "created_at": p.get("create_at"),
            })
        return formatted

    async def wait_for_agent_responses(
        self,
        after_timestamp: int,
        channel_id: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        poll_interval: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Poll channel using non-blocking asyncio.sleep for real agent replies created after timestamp."""
        target_channel = channel_id or await self.get_channel_id()
        timeout = timeout_seconds if timeout_seconds is not None else SWITCH_POLL_TIMEOUT
        interval = poll_interval if poll_interval is not None else SWITCH_POLL_INTERVAL
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            try:
                posts = await self.fetch_recent_messages(channel_id=target_channel, limit=30)
                new_agent_posts = [
                    p for p in posts
                    if (p.get("created_at") or 0) > after_timestamp and ("-anant" in p.get("username", ""))
                ]
                if new_agent_posts:
                    return new_agent_posts
            except Exception:
                pass
            await asyncio.sleep(interval)
        return []


switch_client = SwitchClient()
