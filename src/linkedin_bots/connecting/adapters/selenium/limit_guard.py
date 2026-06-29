"""LinkedIn's weekly invitation limit: its warning dialogs and HTTP 429."""
import json
import logging
import time

from selenium.webdriver.common.by import By

logger = logging.getLogger("linkedin_bot")

# URL fragments of LinkedIn's invitation endpoint.
# A 429 on these paths means the invite quota is exhausted.
INVITE_ENDPOINT_FRAGMENTS = (
    "voyagerRelationshipsDashMemberRelationships",
    "verifyQuotaAndCreate",
)


class SeleniumLimitGuard:
    def __init__(self, driver, perf_logging, confirm, auto_continue=False):
        self.driver = driver
        self.perf_logging = perf_logging
        self.confirm = confirm
        self.auto_continue = auto_continue

    def check(self):
        return self.check_invitation_limit_warning()

    def rate_limited(self):
        return self.detect_rate_limit_429()

    def check_invitation_limit_warning(self):
        """Check for invite limit dialogs. Returns False if automation must stop."""
        try:
            hard_limit_elements = self.driver.find_elements(
                By.XPATH,
                "//h2[contains(text(), 'reached the weekly invitation limit')] | "
                "//h2[@id='ip-fuse-limit-alert__header' and contains(text(), 'reached the weekly')] | "
                "//div[contains(@class, 'ip-fuse-limit-alert')]//h2[contains(text(), 'reached')]")

            if hard_limit_elements:
                logger.error("Weekly invitation limit reached. Stopping automation.")
                try:
                    got_it = self.driver.find_element(
                        By.XPATH,
                        "//button[.//span[text()='Got it']] | "
                        "//button[contains(@class, 'ip-fuse-limit-alert__primary-action')]")
                    self.driver.execute_script("arguments[0].click();", got_it)
                except Exception:
                    try:
                        self.driver.find_element(
                            By.XPATH, "//button[@aria-label='Dismiss']")
                    except Exception:
                        pass
                return False

            warning_elements = self.driver.find_elements(
                By.XPATH,
                "//h2[contains(text(), 'close to the weekly invitation limit')] | "
                "//div[contains(@class, 'ip-fuse-limit-alert')]//h2[contains(text(), 'close to')]")

            if warning_elements:
                logger.warning("Close to the weekly invitation limit!")

                if self.auto_continue:
                    logger.info("Auto-continue enabled (-y). Continuing past the warning.")
                    got_it = self.driver.find_element(
                        By.XPATH,
                        "//button[.//span[text()='Got it']] | "
                        "//button[contains(@class, 'ip-fuse-limit-alert__primary-action')]")
                    self.driver.execute_script("arguments[0].click();", got_it)
                    time.sleep(1)
                    return True
                else:
                    if self.confirm("\nUse remaining invites? (y/N): "):
                        logger.info("Continuing automation.")
                        got_it = self.driver.find_element(
                            By.XPATH,
                            "//button[.//span[text()='Got it']] | "
                            "//button[contains(@class, 'ip-fuse-limit-alert__primary-action')]")
                        self.driver.execute_script("arguments[0].click();", got_it)
                        time.sleep(1)
                        return True
                    else:
                        logger.info("Stopping to save remaining invites.")
                        return False

            return True
        except Exception as e:
            logger.error(f"Error checking invitation limit: {e}")
            return True

    def _drain_performance_logs(self):
        """Return newly buffered performance-log messages as parsed dicts."""
        if not self.perf_logging:
            return []
        try:
            raw = self.driver.get_log("performance")
        except Exception as e:
            logger.debug(f"Could not read performance log: {type(e).__name__}: {e}")
            return []

        messages = []
        for entry in raw:
            try:
                messages.append(json.loads(entry["message"])["message"])
            except Exception:
                continue
        return messages

    def _log_quota_from_invite_response(self, request_id, headers):
        """Log any rate-limit headers from a successful invite response (future-proofing)."""
        quota_headers = {k: v for k, v in headers.items()
                         if any(kw in k.lower() for kw in
                                ("ratelimit", "x-rate-limit", "quota", "remaining"))}
        if quota_headers:
            logger.info(f"[QUOTA] Invite endpoint quota headers: {quota_headers}")

    def detect_rate_limit_429(self, wait=3.0):
        """Watch network traffic for HTTP 429 on the invite endpoint.

        LinkedIn answers 429 when the quota is spent — sometimes without any UI
        dialog. Returns True (and stops) if such a 429 is detected.
        """
        if not self.perf_logging:
            return False

        end = time.time() + wait
        while True:
            for msg in self._drain_performance_logs():
                if msg.get("method") != "Network.responseReceived":
                    continue
                params = msg.get("params", {})
                response = params.get("response", {})
                url = response.get("url", "")
                if not any(frag in url for frag in INVITE_ENDPOINT_FRAGMENTS):
                    continue
                status = response.get("status")
                if status == 429:
                    logger.error(
                        "HTTP 429 from LinkedIn's invitation endpoint — "
                        "quota exhausted. Stopping.")
                    return True
                if status in (200, 201):
                    self._log_quota_from_invite_response(
                        params.get("requestId"), response.get("headers", {}))
            if time.time() >= end:
                return False
            time.sleep(0.5)
