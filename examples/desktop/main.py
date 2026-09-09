"""Exercise screenshots, computer controls, and a noVNC connection."""

from __future__ import annotations

import struct
import time

from createos import (
    APIError,
    Client,
    ComputerOpenRequest,
    ComputerPoint,
    ComputerScreenID,
    ComputerScreenOptions,
    ComputerScreenshotOptions,
    CreateSandboxRequest,
)

_SCREEN = ComputerScreenID.SCREEN_0


def _wait_for_desktop(computer, options):
    """Poll screen geometry while the graphical session starts."""
    deadline = time.monotonic() + 120
    last_error = None
    while time.monotonic() < deadline:
        try:
            return computer.screen(options)
        except APIError as error:
            last_error = error
            time.sleep(2)
    raise TimeoutError(f"desktop did not become ready: {last_error}")


def _screenshot_size(computer, options) -> tuple[int, int]:
    """Read dimensions from the PNG IHDR header without extra dependencies."""
    with computer.screenshot(options) as screenshot:
        payload = screenshot.read()
    if len(payload) < 24 or payload[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError("screenshot was not a valid PNG")
    # PNG stores width and height as big-endian integers in the IHDR chunk.
    return struct.unpack(">II", payload[16:24])


def main() -> None:
    """Verify the desktop computer API end to end."""
    with Client() as client:
        sandbox = client.create_sandbox(
            CreateSandboxRequest(
                shape="s-2vcpu-4gb",
                rootfs="desktop:1",
                ingress_enabled=True,
            )
        )
        print(f"created: {sandbox.id}")
        try:
            computer = sandbox.computer
            screen_options = ComputerScreenOptions(screen_id=_SCREEN)
            print("\n[1/5] reading primary screen...")
            geometry = _wait_for_desktop(computer, screen_options)
            screens = computer.screens.list()
            primary = computer.screens.get(_SCREEN)
            print(f"      geometry: {geometry.width}x{geometry.height}")
            print(
                "      screens: "
                + ", ".join(str(screen.screen_id) for screen in screens)
            )
            print(
                f"      primary display: {primary.display}, "
                f"noVNC port {primary.novnc_port}"
            )

            print("\n[2/5] capturing PNG screenshots...")
            full_size = _screenshot_size(
                computer,
                ComputerScreenshotOptions(
                    screen_id=_SCREEN,
                    timeout=45,
                ),
            )
            print(f"      full screenshot: {full_size[0]}x{full_size[1]}")
            region_size = _screenshot_size(
                computer,
                ComputerScreenshotOptions(
                    screen_id=_SCREEN,
                    timeout=45,
                    x=0,
                    y=0,
                    width=240,
                    height=160,
                ),
            )
            print(f"      region screenshot: {region_size[0]}x{region_size[1]}")

            print("\n[3/5] moving cursor and round-tripping clipboard...")
            target = ComputerPoint(
                x=min(max(geometry.width // 3, 10), geometry.width - 1),
                y=min(max(geometry.height // 3, 10), geometry.height - 1),
            )
            computer.mouse.move(target, screen_options)
            cursor = computer.cursor(screen_options)
            print(f"      cursor: {cursor.x},{cursor.y}")
            clipboard_text = f"CreateOS desktop {sandbox.id}"
            computer.set_clipboard(clipboard_text, screen_options)
            clipboard = computer.clipboard(screen_options)
            print(f"      clipboard: {clipboard.text}")

            print("\n[4/5] opening a URL in the desktop browser...")
            target_url = "https://example.com"
            computer.open(ComputerOpenRequest(target=target_url))
            print(f"      opened: {target_url}")

            print("\n[5/5] creating live noVNC connection...")
            connection = computer.screens.connect(_SCREEN)
            print(f"      screen: {connection.screen_id}")
            print(f"      expires: {connection.expires_at}")
            print(f"      noVNC URL: {connection.url or '(not available)'}")

            if not screens or primary.screen_id is not _SCREEN:
                raise RuntimeError("primary screen was not listed")
            if full_size != (geometry.width, geometry.height):
                raise RuntimeError("full screenshot dimensions did not match")
            if region_size != (240, 160):
                raise RuntimeError("region screenshot dimensions did not match")
            if cursor != target:
                raise RuntimeError("cursor did not move")
            if clipboard.text != clipboard_text:
                raise RuntimeError("clipboard round trip failed")
            if not connection.url.startswith("https://"):
                raise RuntimeError("noVNC connection omitted an HTTPS URL")
            print("\nverified desktop computer API and noVNC connection")
        finally:
            sandbox.destroy()
            print("destroyed")


if __name__ == "__main__":
    main()
