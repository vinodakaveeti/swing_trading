import os
import pyotp
import requests
from SmartApi import SmartConnect   # pip package: smartapi-python
from dotenv import load_dotenv

load_dotenv()   # loads .env into os.environ

def escape_telegram_text(text: str) -> str:
    """Escape Telegram Markdown special characters in text for safe insertion."""
    if not isinstance(text, str):
        text = str(text)
    # Escape _ and * to prevent them from being interpreted as Markdown formatting
    return text.replace('_', r'\_').replace('*', r'\*')


class AngelOneAPI:
    """
    Minimal wrapper: login + get_ltp.
    All other SmartAPI methods can be added later if needed.
    Implemented as singleton to ensure only one login session.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Initialize only once
            cls._instance._initialized = False
        return cls._instance

    def __init__(self,
                 api_key=None,
                 client_id=None,
                 password=None,
                 totp_key=None,
                 pin=None):
        # Prevent re-initialization
        if getattr(self, '_initialized', False):
            return

        # Prefer explicit args, fallback to env vars
        self.api_key    = api_key    or os.getenv("ANGEL_API_KEY")
        self.client_id  = client_id  or os.getenv("ANGEL_CLIENT_ID")
        self.password   = password   or os.getenv("ANGEL_PASSWORD")
        self.totp_key   = totp_key   or os.getenv("ANGEL_TOTP_KEY")
        self.pin        = pin        or os.getenv("ANGEL_PIN")

        if not all([self.api_key, self.client_id,
                    self.password or self.pin, self.totp_key]):
            raise ValueError("Missing Angel One credentials – check .env")

        self.base_url = "https://apiconnect.angelone.in"
        self.access_token = None
        self.refresh_token = None
        self.feed_token = None

        # Initialise SmartConnect (requires only api_key for now)
        self.smart = SmartConnect(api_key=self.api_key)

        self._initialized = True

    # -----------------------------------------------------------------
    # Authentication helpers
    # -----------------------------------------------------------------
    def _get_totp(self) -> str:
        """Return current TOTP string."""
        return pyotp.TOTP(self.totp_key).now()

    def login(self) -> bool:
        """Logs in using SmartAPI; stores tokens for later calls."""
        if self.access_token:          # already logged in
            return True

        totp = self._get_totp()
        try:
            # generateSession returns dict with status, message, data
            resp = self.smart.generateSession(
                self.client_id,
                self.pin or self.password,   # SmartAPI expects PIN; if you use password, put it here
                totp
            )
            if not resp.get("status"):
                raise Exception(f"Login failed: {resp.get('message')}")

            data = resp["data"]
            # The JWT token from login response already has "Bearer " prefix
            # But we need to store the raw token for the Authorization header
            # The SmartAPI library stores the raw token internally, so we use that
            self.access_token = self.smart.access_token  # Get raw token from SmartAPI instance
            self.refresh_token = data["refreshToken"]
            self.feed_token   = data.get("feedToken")
            # Set the auth header on the SmartConnect session (already done by login, but ensure consistency)
            self.smart.setAccessToken(self.access_token)
            self.smart.setRefreshToken(self.refresh_token)
            self.smart.setFeedToken(self.feed_token)
            return True
        except Exception as e:
            raise Exception(f"Angel One login error: {e}")

    def logout(self) -> None:
        """Invalidate the session."""
        if self.access_token:
            try:
                self.smart.terminateSession(self.client_id)
            except Exception:
                pass
            self.access_token = self.refresh_token = self.feed_token = None

    # -----------------------------------------------------------------
    # Market data – LTP (Last Traded Price)
    # -----------------------------------------------------------------
    def get_ltp(self, exchange: str, tradingsymbol: str, symboltoken: str) -> float:
        """
        Returns the latest price for a given instrument.
        Raises Exception on failure.
        """
        if not self.access_token:
            raise RuntimeError("Not logged in – call login() first")

        params = {
            "exchange": exchange,
            "tradingsymbol": tradingsymbol,
            "symboltoken": symboltoken
        }
        try:
            resp = self.smart.ltpData(
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                symboltoken=symboltoken
            )
            if not resp.get("status"):
                raise Exception(f"LTP error: {resp.get('message')}")

            # SmartAPI returns: {"status":True, "message":"", "data":{"ltp":<float>}}
            ltp = float(resp["data"]["ltp"])
            return ltp
        except Exception as e:
            raise Exception(f"Failed to fetch LTP for {tradingsymbol}: {e}")

    # -----------------------------------------------------------------
    # Market data – Top performers / screener
    # -----------------------------------------------------------------
    def get_top_nse_performers(self, limit: int = 100,
                               criteria: str = "percent_change") -> list[dict]:
        """
        Fetch the top NSE performers.
        Tries to use the gainersLosers endpoint with datatype='PercPriceGainers'
        to get top gaining derivatives, then maps to underlying equity symbols.
        If that fails, falls back to a predefined Nifty 50 list.

        Parameters
        ----------
        limit : int
            How many stocks to return.
        criteria : str
            Sorting criterion – only "percent_change" is supported for this
            implementation (maps to "PercPriceGainers").

        Returns
        -------
        list[dict]
            Each dict contains at least:
                {
                    "symbol": "RELIANCE",
                    "exchange": "NSE",
                    "symboltoken": "317",
                    "ltp": 2450.30,
                    "change": 12.5,
                    "percent_change": 0.51,
                    "volume": 123456,
                    "value": 302456789.0
                }
        """
        if not self.access_token:
            raise RuntimeError("Not logged in – call login() first")

        # Map criteria to datatype for gainersLosers endpoint
        if criteria.lower() in ("percent_change", "percentchange", "pct_change"):
            datatype = "PercPriceGainers"
        else:
            # For other criteria we could extend; for now fall back to static list
            datatype = None

        if datatype:
            try:
                # Request more than needed to allow for filtering and deduplication
                request_count = min(limit * 3, 200)  # API may have max
                params = {
                    "exchange": "NSE",
                    "datatype": datatype,
                    "count": request_count,
                    "expirytype": "NEAR"  # near month futures
                }
                url = f"{self.base_url}/rest/secure/angelbroking/marketData/v1/gainersLosers"
                headers = self.requestHeaders()
                headers["Authorization"] = f"Bearer {self.access_token}"
                headers["Content-Type"] = "application/json"
                import requests
                resp = requests.post(url, json=params, headers=headers, timeout=10)
                if resp.status_code != 200:
                    raise Exception(f"HTTP {resp.status_code}: {resp.text}")
                data = resp.json()
                if not data.get("status"):
                    # If the API returns an error in the JSON body
                    raise Exception(data.get("message", "Unknown error"))
                raw_items = data.get("data", [])
                # Process items to extract equity symbols
                results = []
                seen = set()
                import re
                for item in raw_items:
                    ts = item.get("tradingSymbol", "")
                    # Extract underlying symbol: leading letters only
                    m = re.match(r'^([A-Z]+)', ts)
                    if not m:
                        continue
                    underlying = m.group(1)
                    if underlying in seen:
                        continue
                    # Look up equity instrument for this underlying
                    try:
                        search_res = self.smart.searchScrip("NSE", underlying)
                        if not search_res.get("status"):
                            continue
                        eq_info = None
                        for instr in search_res.get("data", []):
                            if instr.get("tradingsymbol", "").endswith("-EQ"):
                                eq_info = instr
                                break
                        if not eq_info:
                            # fallback: take first instrument (should be EQ usually)
                            eq_info = search_res.get("data", [{}])[0]
                        symbol = eq_info.get("tradingsymbol", "").replace("-EQ", "")
                        exchange = eq_info.get("exchange", "NSE")
                        symboltoken = eq_info.get("symboltoken")
                        if not symbol or not symboltoken:
                            continue
                        # Fetch equity LTP (more accurate than futures LTP)
                        ltp = self.get_ltp(eq_info["exchange"], f"{symbol}-EQ", eq_info["symboltoken"])
                        change = float(item.get("netChange", 0.0))
                        percent_change = float(item.get("percentChange", 0.0))
                        # Volume and value not available from this endpoint; set to 0
                        volume = 0
                        value = 0.0
                        results.append({
                            "symbol": symbol,
                            "exchange": exchange,
                            "symboltoken": str(symboltoken),
                            "ltp": ltp,
                            "change": change,
                            "percent_change": percent_change,
                            "volume": volume,
                            "value": value,
                        })
                        seen.add(underlying)
                        if len(results) >= limit:
                            break
                    except Exception as e:
                        # Skip this symbol and continue
                        continue
                if results:
                    return results
                # If we got no results, fall through to static fallback
            except Exception as e:
                # Log and fall back to static list
                # In a real app, you might log this; we'll just continue to fallback
                pass
        # Fallback to static Nifty 50 list
        NIFTY_50 = [
            "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "APOLLOTYRE", "ASIANPAINT",
            "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG",
            "BEL", "BHARTIARTL", "BIOCON", "BPCL", "BRITANNIA", "CIPLA",
            "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT", "GAIL", "GRASIM",
            "HCLTECH", "HDFC", "HDFCBANK", "HEROMOTOCO", "HINDALCO", "HAL",
            "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "IOC", "ITC",
            "JSWSTEEL", "KOTAKBANK", "LT", "LTIM", "M&M", "MARUTI", "NESTLEIND",
            "NTPC", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHREECEM",
            "SHRIRAMFIN", "SUNPHARMA", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
            "TCS", "TECHM", "TITAN", "ULTRACEMCO", "UPL", "WIPRO"
        ]
        results = []
        for sym in NIFTY_50[:limit]:
            try:
                info = self.symbol_lookup(sym)
                ltp = self.get_ltp(info["exchange"], f"{sym}-EQ", info["symboltoken"])
                # For fallback we don't have change/percent_change; set to 0
                results.append({
                    "symbol": sym,
                    "exchange": info["exchange"],
                    "symboltoken": info["symboltoken"],
                    "ltp": ltp,
                    "change": 0.0,
                    "percent_change": 0.0,
                    "volume": 0,
                    "value": 0.0,
                })
            except Exception:
                # If lookup fails, skip
                continue
        return results

    # -----------------------------------------------------------------
    # Helper methods
    # -----------------------------------------------------------------
    def requestHeaders(self):
        return {
            'Content-type': 'application/json',
            'Accept': 'application/json',
            'X-UserType': 'USER',
            'X-SourceID': 'WEB',
            'X-ClientLocalIP': 'CLIENT_LOCAL_IP',
            'X-ClientPublicIP': 'CLIENT_PUBLIC_IP',
            'X-MACAddress': 'MAC_ADDRESS',
            'X-PrivateKey': self.api_key
        }

    @staticmethod
    def symbol_lookup(symbol: str) -> dict:
        """
        Very small static map for the 10‑stock watch‑list.
        In a production system you would download the scrip master
        and look up the token dynamically.
        """
        # NSE equity symbols → (exchange, symboltoken)
        MAP = {
            "RELIANCE": ("NSE", "2885"),
            "TCS":      ("NSE", "11536"),
            "HDFCBANK": ("NSE", "1333"),
            "INFY":     ("NSE", "1594"),
            "ICICIBANK":("NSE", "4963"),
            "HDFC":     ("NSE", "1330"),
            "SBIN":     ("NSE", "3045"),
            "BHARTIARTL":("NSE","10604"),
            "KOTAKBANK":("NSE","17818"),
            "LT":       ("NSE","11483")
        }
        if symbol not in MAP:
            raise KeyError(f"Symbol {symbol} not in watch‑list")
        exch, tok = MAP[symbol]
        return {"exchange": exch, "symbol": f"{symbol}-EQ", "symboltoken": tok}

    # -----------------------------------------------------------------
    # Report generation and Telegram notification
    # -----------------------------------------------------------------
    def generate_top_performers_report(self, limit: int = 10) -> str:
        """
        Generate a formatted report of top NSE performers.

        Args:
            limit: Number of top performers to include in report

        Returns:
            Formatted report string suitable for Telegram
        """
        if not self.access_token:
            raise RuntimeError("Not logged in – call login() first")

        # Get top performers
        top_performers = self.get_top_nse_performers(limit=limit, criteria="percent_change")

        if not top_performers:
            return "[WARN] No top performers data received"

        # Generate report message
        from datetime import datetime
        report = f"📊 *Top {limit} NSE Performers*\n\n"
        report += f"_As of {escape_telegram_text(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}_\n\n"

        for i, stock in enumerate(top_performers, 1):
            symbol = stock.get('symbol', 'N/A')
            ltp = stock.get('ltp', 0.0)
            change = stock.get('change', 0.0)
            percent_change = stock.get('percent_change', 0.0)
            volume = stock.get('volume', 0)

            # Format change with emoji
            change_emoji = "📈" if change >= 0 else "📉"
            change_str = f"{change:+.2f} ({percent_change:+.2f}%)"

            # Format volume
            if volume >= 10000000:
                volume_str = f"{volume/1000000:.1f}M"
            elif volume >= 10000:
                volume_str = f"{volume/1000:.0f}K"
            else:
                volume_str = str(volume)

            report += f"{i}. *{escape_telegram_text(symbol)}*{change_emoji}\n"
            report += f"   LTP: ₹{ltp:.2f}\n"
            report += f"   Change: {change_str}\n"
            report += f"   Volume: {volume_str}\n\n"

        # Add summary
        gainers = sum(1 for s in top_performers if s.get('change', 0) > 0)
        losers = sum(1 for s in top_performers if s.get('change', 0) < 0)
        report += f"📊 Summary: {gainers} gainers, {losers} losers\n"

        return report

    def send_report_via_telegram(self, report: str) -> bool:
        """
        Send a report via Telegram bot.

        Args:
            report: The report message to send

        Returns:
            True if successful, False otherwise
        """
        # Telegram Notification Settings
        TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Get from @BotFather
        TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Your chat ID
        TELEGRAM_ENABLED = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

        if not TELEGRAM_ENABLED:
            print("[INFO] Telegram notifications disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
            return False

        try:
            import requests
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": report,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"[WARN] Telegram message failed: {response.text}")
                return False
            else:
                print("[INFO] Telegram message sent successfully")
                return True
        except Exception as e:
            print(f"[WARN] Failed to send Telegram message: {e}")
            return False


# -----------------------------------------------------------------
# Main execution - runs only once when script is executed directly
# -----------------------------------------------------------------
import sys

if __name__ == "__main__":
    print("=" * 60)
    print("Angel One Top Performers Report Generator")
    print("=" * 60)

    try:
        # Initialize Angel One API (singleton - init runs only once)
        api = AngelOneAPI()

        # Login
        print("[INFO] Logging in to Angel One...")
        if not api.login():
            print("[ERROR] Failed to login to Angel One API")
            sys.exit(1)

        print("[INFO] Generating top performers report...")
        # Generate report
        report = api.generate_top_performers_report(limit=10)

        print("\n" + "=" * 60)
        print("Generated Report:")
        print("=" * 60)
        print(report)

        # Send via Telegram
        print("\n[INFO] Sending report via Telegram...")
        success = api.send_report_via_telegram(report)
        if success:
            print("[INFO] Report sent successfully via Telegram!")
        else:
            print("[WARN] Failed to send report via Telegram (check configuration)")

        # Logout
        api.logout()
        print("[INFO] Logged out from Angel One")

        print("\n[INFO] Execution completed successfully.")
        sys.exit(0)

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        sys.exit(1)