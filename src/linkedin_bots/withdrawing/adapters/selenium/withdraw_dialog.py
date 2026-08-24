"""LinkedIn's withdrawal confirmation dialog."""

import logging
import time

logger = logging.getLogger("linkedin_bot")

# Shadow hosts LinkedIn renders modals into — same ones the connect bot uses.
_SHADOW_HOSTS = ("#interop-outlet", "[data-testid='interop-shadowdom']")
# The withdrawal confirmation dialog ("If you withdraw now, you won't be able
# to resend to this person for up to 3 weeks."). Its confirm button repeats
# the invitee's name in aria-label, which is what lets the bot check the
# dialog belongs to the card it just clicked. Cancel sits right beside it, so
# text matching stays exact — never a substring.
_DIALOG = "dialog[open], [role='dialog'][open], [data-testid='dialog'][open]"
_CONFIRM_BUTTON = (
    "dialog[open] button[aria-label^='Withdraw invitation sent to'], "
    "dialog[open] button[aria-label^='Retirar convite'], "
    "[role='dialog'] button[aria-label^='Withdraw invitation sent to'], "
    "[role='dialog'] button[aria-label^='Retirar convite']"
)
_CONFIRM_LABELS = ("withdraw", "retirar", "remover")
_CANCEL_LABELS = ("cancel", "cancelar", "dismiss", "fechar")


class WithdrawDialog:
    """The "Withdraw invitation?" dialog, checked against the card that opened it."""

    def __init__(self, driver, clicker):
        self.driver = driver
        self._click = clicker._robust_click

    def find_confirm_button(self):
        """The confirm button of LinkedIn's withdrawal dialog, or None.

        The dialog is a light-DOM ``<dialog open>`` whose confirm button is
        ``button[aria-label^='Withdraw invitation sent to …']`` — matched
        first, because that label is also how the button is checked against
        the right person. Falling back to button text keeps a build that
        renames the label working, and the ``#interop-outlet`` shadow host is
        still searched since the connect bot's modals live there.

        Note the sibling ``Cancel`` button: matching on text alone has to stay
        exact, or a substring rule would happily confirm the wrong control.
        """
        try:
            precise = self.driver.execute_script(
                "return document.querySelector(arguments[0]);", _CONFIRM_BUTTON)
            if precise is not None:
                return precise
        except Exception as e:
            logger.debug(f"Precise confirm lookup failed: {type(e).__name__}: {e}")

        try:
            return self.driver.execute_script(
                "const [labels, hostSel] = arguments;"
                "const roots = [document];"
                "hostSel.forEach(s => document.querySelectorAll(s).forEach(h => {"
                "  if (h.shadowRoot) roots.push(h.shadowRoot);"
                "}));"
                "for (const root of roots) {"
                "  const dialogs = root.querySelectorAll("
                "    \"dialog[open], [role='dialog'], [data-test-modal]\");"
                "  for (const d of dialogs) {"
                "    const hit = [...d.querySelectorAll(\"button, a[role='button']\")]"
                "      .find(b => labels.includes((b.innerText || '').trim().toLowerCase())"
                "                 && b.offsetParent !== null);"
                "    if (hit) return hit;"
                "  }"
                "}"
                "return null;",
                list(_CONFIRM_LABELS), list(_SHADOW_HOSTS))
        except Exception as e:
            logger.debug(f"Could not look for a confirm button: "
                         f"{type(e).__name__}: {e}")
            return None

    def dismiss(self):
        """Close an open dialog via its Cancel button, then its own close().

        A modal ``<dialog>`` blocks the page underneath it, so a confirmation
        left standing after a failed withdrawal would break every click that
        follows. Clearing it is what keeps one bad card from ending the run.
        """
        try:
            cancel = self.driver.execute_script(
                "const d = document.querySelector(arguments[0]);"
                "if (!d) return null;"
                "const labels = arguments[1];"
                "return [...d.querySelectorAll('button')].find(b => {"
                "  const t = ((b.innerText || '') + ' ' +"
                "    (b.getAttribute('aria-label') || '')).trim().toLowerCase();"
                "  return labels.some(l => t === l);"
                "}) || null;",
                _DIALOG, list(_CANCEL_LABELS))
        except Exception:
            cancel = None

        if cancel is not None:
            self._click(cancel, "dialog cancel")
        else:
            try:
                self.driver.execute_script(
                    "const d = document.querySelector(arguments[0]);"
                    "if (d && d.close) d.close();", _DIALOG)
            except Exception:
                pass
        time.sleep(0.5)

    def confirm(self, name, timeout=6):
        """Click Withdraw in the confirmation dialog.

        The dialog's confirm button carries the invitee's name in its
        ``aria-label`` ("Withdraw invitation sent to Camilla Souza"), so the
        dialog is checked against the card that opened it. A mismatch — a
        dialog left over from a previous card, or one opened by a mis-aimed
        click — is dismissed rather than confirmed: withdrawing the wrong
        person is not recoverable, and a skipped card is.

        Returns True when the dialog was confirmed.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            button = self.find_confirm_button()
            if button is not None:
                try:
                    label = (button.get_attribute("aria-label") or "").strip()
                except Exception:
                    label = ""
                if name and label and name.lower() not in label.lower():
                    logger.warning(
                        f"Confirmation dialog reads '{label}' but the card was "
                        f"{name} — dismissing it instead of withdrawing.")
                    self.dismiss()
                    return False
                self._click(button, f"withdrawal confirm ({name})")
                return True
            time.sleep(0.3)
        logger.debug(f"No confirmation dialog appeared for {name}.")
        return False
