#!/usr/bin/env python3
"""
ADB Controller - Android Debug Bridge operations module

This module provides comprehensive ADB functionality for controlling Android devices,
including connection management, command execution, UI interactions, and device monitoring.

Author: Google Account Creator Team
Version: 0.1.0
"""

import asyncio
import logging
import os
import random
import time
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

from adb_shell import AdbDeviceTcp, AdbDeviceUsb
from adb_shell.adb_device import AdbDevice
from adb_shell.exceptions import TcpTimeoutException, DeviceAuthTimeoutError
import cv2
import numpy as np
from PIL import Image

# Configure logging
logger = logging.getLogger(__name__)

class ADBConnectionError(Exception):
    """Custom exception for ADB connection issues."""
    pass

class ADBCommandError(Exception):
    """Custom exception for ADB command execution issues."""
    pass

class ADBController:
    """
    Comprehensive ADB controller for Android device operations.
    
    This class provides methods for connecting to Android devices via ADB,
    executing commands, simulating user interactions, and capturing screenshots.
    """
    
    def __init__(self, device_id: Optional[str] = None, connection_timeout: int = 30):
        """
        Initialize ADB Controller.
        
        Args:
            device_id: Specific device ID to connect to (optional)
            connection_timeout: Connection timeout in seconds
        """
        self.device_id = device_id
        self.connection_timeout = connection_timeout
        self.device: Optional[AdbDevice] = None
        self.is_connected = False
        self.device_info: Dict[str, str] = {}
        
        # Create screenshots directory if it doesn't exist
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        
        logger.info(f"ADB Controller initialized for device: {device_id or 'auto-detect'}")

    def connect_device(self, host: str = None, port: int = 5555) -> bool:
        """
        Establish connection to Android device via ADB.
        
        Args:
            host: IP address for TCP connection (None for USB)
            port: Port number for TCP connection
            
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            ADBConnectionError: If connection fails after retries
        """
        try:
            if host:
                # TCP connection (wireless ADB)
                logger.info(f"Attempting TCP connection to {host}:{port}")
                self.device = AdbDeviceTcp(host, port, default_timeout_s=self.connection_timeout)
            else:
                # USB connection
                logger.info(f"Attempting USB connection to device: {self.device_id or 'auto-detect'}")
                self.device = AdbDeviceUsb()
            
            # Connect with authentication
            self.device.connect(rsa_keys=[], auth_timeout_s=self.connection_timeout)
            
            # Verify connection
            if self._verify_connection():
                self.is_connected = True
                self._get_device_info()
                logger.info(f"Successfully connected to device: {self.device_info.get('model', 'Unknown')}")
                return True
            else:
                raise ADBConnectionError("Device verification failed")
                
        except (TcpTimeoutException, DeviceAuthTimeoutError) as e:
            logger.error(f"Connection timeout: {e}")
            raise ADBConnectionError(f"Connection timeout: {e}")
        except Exception as e:
            logger.error(f"ADB connection failed: {e}")
            raise ADBConnectionError(f"ADB connection failed: {e}")

    def _verify_connection(self) -> bool:
        """
        Verify ADB connection is working properly.
        
        Returns:
            bool: True if connection is verified
        """
        try:
            # Test with a simple command
            result = self.device.shell("echo 'connection_test'", timeout_s=5)
            return "connection_test" in result.strip()
        except Exception as e:
            logger.error(f"Connection verification failed: {e}")
            return False

    def _get_device_info(self) -> None:
        """Retrieve and store device information."""
        try:
            properties = [
                ("model", "ro.product.model"),
                ("brand", "ro.product.brand"),
                ("version", "ro.build.version.release"),
                ("sdk", "ro.build.version.sdk"),
                ("serial", "ro.serialno"),
                ("density", "ro.sf.lcd_density"),
            ]
            
            for key, prop in properties:
                try:
                    result = self.device.shell(f"getprop {prop}", timeout_s=5)
                    self.device_info[key] = result.strip()
                except Exception:
                    self.device_info[key] = "Unknown"
                    
            logger.info(f"Device info retrieved: {self.device_info}")
            
        except Exception as e:
            logger.error(f"Failed to get device info: {e}")

    def execute_shell_command(self, command: str, timeout: int = 30, retry_count: int = 2) -> str:
        """
        Execute a shell command on the connected device.
        
        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds
            retry_count: Number of retry attempts on failure
            
        Returns:
            str: Command output
            
        Raises:
            ADBCommandError: If command execution fails
            ADBConnectionError: If device is not connected
        """
        if not self.is_connected or not self.device:
            raise ADBConnectionError("Device is not connected")
        
        for attempt in range(retry_count + 1):
            try:
                logger.debug(f"Executing command (attempt {attempt + 1}): {command}")
                result = self.device.shell(command, timeout_s=timeout)
                logger.debug(f"Command output: {result[:200]}...")  # Log first 200 chars
                return result
                
            except Exception as e:
                if attempt < retry_count:
                    logger.warning(f"Command execution failed (attempt {attempt + 1}), retrying: {e}")
                    time.sleep(1)  # Brief delay before retry
                else:
                    logger.error(f"Command execution failed after {retry_count + 1} attempts: {e}")
                    raise ADBCommandError(f"Failed to execute command '{command}': {e}")

    def execute_shell_command_with_return_code(self, command: str, timeout: int = 30) -> Tuple[str, int]:
        """
        Execute a shell command and return both output and return code.
        
        Args:
            command: Shell command to execute
            timeout: Command timeout in seconds
            
        Returns:
            Tuple[str, int]: (output, return_code)
            
        Raises:
            ADBCommandError: If command execution fails
        """
        try:
            # Wrap command to capture return code
            wrapped_command = f"{command}; echo \"RETURN_CODE:$?\""
            result = self.execute_shell_command(wrapped_command, timeout)
            
            # Parse output and return code
            lines = result.strip().split('\n')
            return_code_line = lines[-1]
            
            if return_code_line.startswith("RETURN_CODE:"):
                return_code = int(return_code_line.split(":")[-1])
                output = '\n'.join(lines[:-1])
                return output, return_code
            else:
                # Fallback if return code parsing fails
                return result, 0
                
        except Exception as e:
            raise ADBCommandError(f"Failed to execute command with return code: {e}")

    def execute_root_command(self, command: str, timeout: int = 30) -> str:
        """
        Execute a command with root privileges (requires rooted device).
        
        Args:
            command: Command to execute as root
            timeout: Command timeout in seconds
            
        Returns:
            str: Command output
            
        Raises:
            ADBCommandError: If root command execution fails
        """
        try:
            # Check if device is rooted
            if not self.is_device_rooted():
                raise ADBCommandError("Device is not rooted or su is not available")
            
            root_command = f"su -c '{command}'"
            return self.execute_shell_command(root_command, timeout)
            
        except Exception as e:
            raise ADBCommandError(f"Failed to execute root command: {e}")

    def is_device_rooted(self) -> bool:
        """
        Check if the device has root access.
        
        Returns:
            bool: True if device is rooted and su is accessible
        """
        try:
            # Try to execute a simple su command
            result = self.execute_shell_command("which su", timeout=10)
            return bool(result.strip())
        except:
            return False

    def get_system_property(self, property_name: str) -> str:
        """
        Get a system property value.
        
        Args:
            property_name: Property name (e.g., 'ro.product.model')
            
        Returns:
            str: Property value or empty string if not found
        """
        try:
            result = self.execute_shell_command(f"getprop {property_name}", timeout=10)
            return result.strip()
        except Exception as e:
            logger.error(f"Failed to get property {property_name}: {e}")
            return ""

    def set_system_property(self, property_name: str, value: str) -> bool:
        """
        Set a system property value (requires root).
        
        Args:
            property_name: Property name to set
            value: Property value to set
            
        Returns:
            bool: True if property was set successfully
        """
        try:
            self.execute_root_command(f"setprop {property_name} '{value}'", timeout=10)
            # Verify the property was set
            current_value = self.get_system_property(property_name)
            return current_value == value
        except Exception as e:
            logger.error(f"Failed to set property {property_name}: {e}")
            return False

    def install_apk(self, apk_path: str, replace: bool = True) -> bool:
        """
        Install an APK file on the device.
        
        Args:
            apk_path: Path to the APK file
            replace: Whether to replace existing app
            
        Returns:
            bool: True if installation successful
        """
        try:
            if not os.path.exists(apk_path):
                raise ADBCommandError(f"APK file not found: {apk_path}")
            
            # Push APK to device
            device_path = f"/data/local/tmp/{os.path.basename(apk_path)}"
            self.device.push(apk_path, device_path)
            
            # Install APK
            flags = "-r" if replace else ""
            result = self.execute_shell_command(f"pm install {flags} {device_path}", timeout=60)
            
            # Clean up temporary file
            self.execute_shell_command(f"rm {device_path}")
            
            return "Success" in result
            
        except Exception as e:
            logger.error(f"APK installation failed: {e}")
            return False

    def uninstall_package(self, package_name: str) -> bool:
        """
        Uninstall a package from the device.
        
        Args:
            package_name: Package name to uninstall
            
        Returns:
            bool: True if uninstallation successful
        """
        try:
            result = self.execute_shell_command(f"pm uninstall {package_name}", timeout=30)
            return "Success" in result
        except Exception as e:
            logger.error(f"Package uninstallation failed: {e}")
            return False

    def get_installed_packages(self) -> List[str]:
        """
        Get list of installed packages on the device.
        
        Returns:
            List[str]: List of package names
        """
        try:
            result = self.execute_shell_command("pm list packages", timeout=30)
            packages = []
            for line in result.strip().split('\n'):
                if line.startswith('package:'):
                    packages.append(line.replace('package:', ''))
            return packages
        except Exception as e:
            logger.error(f"Failed to get installed packages: {e}")
            return []

    def is_package_installed(self, package_name: str) -> bool:
        """
        Check if a specific package is installed.
        
        Args:
            package_name: Package name to check
            
        Returns:
            bool: True if package is installed
        """
        try:
            result = self.execute_shell_command(f"pm list packages {package_name}", timeout=10)
            return f"package:{package_name}" in result
        except Exception as e:
            logger.error(f"Failed to check package installation: {e}")
            return False

    # ========== TEXT INPUT METHODS ==========
    
    def input_text(self, text: str, delay_between_chars: bool = True) -> bool:
        """
        Send text input to the device.
        
        Args:
            text: Text to input
            delay_between_chars: Whether to add delays between characters
            
        Returns:
            bool: True if text input successful
        """
        try:
            if not text:
                return True
            
            # Escape special characters for shell
            escaped_text = self._escape_text_for_input(text)
            
            if delay_between_chars and len(text) > 5:
                # Type character by character with human-like delays
                return self._type_with_delays(escaped_text)
            else:
                # Fast typing for short text
                command = f"input text '{escaped_text}'"
                result = self.execute_shell_command(command, timeout=10)
                logger.debug(f"Text input: {text[:50]}...")
                return True
                
        except Exception as e:
            logger.error(f"Failed to input text: {e}")
            return False

    def _escape_text_for_input(self, text: str) -> str:
        """
        Escape special characters for ADB input command.
        
        Args:
            text: Original text
            
        Returns:
            str: Escaped text
        """
        # Replace problematic characters
        replacements = {
            "'": "\\'",
            '"': '\\"',
            '\\': '\\\\',
            '`': '\\`',
            '$': '\\$',
            '\n': '\\n',
            '\t': '\\t',
            ' ': '%s',  # ADB uses %s for spaces
        }
        
        escaped = text
        for char, replacement in replacements.items():
            escaped = escaped.replace(char, replacement)
            
        return escaped

    def _type_with_delays(self, text: str) -> bool:
        """
        Type text character by character with human-like delays.
        
        Args:
            text: Text to type
            
        Returns:
            bool: True if successful
        """
        try:
            for char in text:
                # Input each character
                if char == ' ':
                    # Use keyevent for space
                    success = self.send_keyevent(62)  # KEYCODE_SPACE
                else:
                    command = f"input text '{char}'"
                    result = self.execute_shell_command(command, timeout=5)
                    success = True
                
                if not success:
                    return False
                
                # Human-like typing delay
                delay = random.uniform(0.05, 0.15)  # 50-150ms between characters
                time.sleep(delay)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to type with delays: {e}")
            return False

    def send_keyevent(self, keycode: int) -> bool:
        """
        Send a key event to the device.
        
        Args:
            keycode: Android keycode (e.g., 4 for BACK, 3 for HOME)
            
        Returns:
            bool: True if keyevent successful
        """
        try:
            command = f"input keyevent {keycode}"
            result = self.execute_shell_command(command, timeout=10)
            
            # Add small delay after keyevent
            time.sleep(random.uniform(0.1, 0.2))
            
            logger.debug(f"Keyevent sent: {keycode}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send keyevent {keycode}: {e}")
            return False

    def press_back(self) -> bool:
        """Press the back button."""
        return self.send_keyevent(4)  # KEYCODE_BACK

    def press_home(self) -> bool:
        """Press the home button."""
        return self.send_keyevent(3)  # KEYCODE_HOME

    def press_menu(self) -> bool:
        """Press the menu button."""
        return self.send_keyevent(82)  # KEYCODE_MENU

    def press_enter(self) -> bool:
        """Press the enter key."""
        return self.send_keyevent(66)  # KEYCODE_ENTER

    def press_delete(self) -> bool:
        """Press the delete/backspace key."""
        return self.send_keyevent(67)  # KEYCODE_DEL

    def press_space(self) -> bool:
        """Press the space key."""
        return self.send_keyevent(62)  # KEYCODE_SPACE

    def press_tab(self) -> bool:
        """Press the tab key."""
        return self.send_keyevent(61)  # KEYCODE_TAB

    def clear_text_field(self, field_x: int = None, field_y: int = None) -> bool:
        """
        Clear a text field by selecting all and deleting.
        
        Args:
            field_x: X coordinate of text field (optional)
            field_y: Y coordinate of text field (optional)
            
        Returns:
            bool: True if successful
        """
        try:
            # Tap on text field if coordinates provided
            if field_x is not None and field_y is not None:
                self.tap(field_x, field_y)
                time.sleep(0.5)
            
            # Select all text (Ctrl+A equivalent on Android)
            self.send_keyevent(29)  # KEYCODE_A
            time.sleep(0.2)
            
            # Delete selected text
            self.send_keyevent(67)  # KEYCODE_DEL
            time.sleep(0.2)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to clear text field: {e}")
            return False

    def input_text_in_field(self, text: str, field_x: int, field_y: int, clear_first: bool = True) -> bool:
        """
        Input text in a specific text field.
        
        Args:
            text: Text to input
            field_x: X coordinate of text field
            field_y: Y coordinate of text field
            clear_first: Whether to clear field before inputting
            
        Returns:
            bool: True if successful
        """
        try:
            # Tap on the text field
            self.tap(field_x, field_y)
            time.sleep(0.5)
            
            # Clear field if requested
            if clear_first:
                self.clear_text_field()
                time.sleep(0.3)
            
            # Input the text
            return self.input_text(text, delay_between_chars=True)
            
        except Exception as e:
            logger.error(f"Failed to input text in field: {e}")
            return False

    def simulate_typing_pattern(self, text: str, typing_speed: str = "normal") -> bool:
        """
        Simulate human-like typing patterns with variable speeds and occasional mistakes.
        
        Args:
            text: Text to type
            typing_speed: "slow", "normal", "fast", or "random"
            
        Returns:
            bool: True if successful
        """
        try:
            # Define speed parameters
            speed_configs = {
                "slow": (0.1, 0.3, 0.05),      # (min_delay, max_delay, mistake_chance)
                "normal": (0.05, 0.15, 0.02),
                "fast": (0.02, 0.08, 0.01),
                "random": (0.02, 0.3, 0.03)
            }
            
            min_delay, max_delay, mistake_chance = speed_configs.get(typing_speed, speed_configs["normal"])
            
            typed_text = ""
            i = 0
            
            while i < len(text):
                char = text[i]
                
                # Simulate occasional typing mistakes
                if random.random() < mistake_chance and len(typed_text) > 2:
                    # Type wrong character then correct it
                    wrong_char = random.choice("abcdefghijklmnopqrstuvwxyz")
                    self.input_text(wrong_char, delay_between_chars=False)
                    time.sleep(random.uniform(0.2, 0.5))
                    self.press_delete()
                    time.sleep(random.uniform(0.1, 0.3))
                
                # Type the correct character
                success = self.input_text(char, delay_between_chars=False)
                if not success:
                    return False
                
                typed_text += char
                
                # Variable delay between characters
                if typing_speed == "random":
                    # Occasional longer pauses (thinking)
                    if random.random() < 0.1:
                        time.sleep(random.uniform(0.5, 1.5))
                    else:
                        time.sleep(random.uniform(min_delay, max_delay))
                else:
                    time.sleep(random.uniform(min_delay, max_delay))
                
                i += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to simulate typing pattern: {e}")
            return False

    def paste_text(self, text: str) -> bool:
        """
        Paste text using clipboard (requires setting clipboard first).
        
        Args:
            text: Text to paste
            
        Returns:
            bool: True if successful
        """
        try:
            # Set clipboard content
            escaped_text = text.replace('"', '\\"')
            clipboard_cmd = f'am broadcast -a clipper.set -e text "{escaped_text}"'
            self.execute_shell_command(clipboard_cmd, timeout=10)
            
            # Wait a moment
            time.sleep(0.3)
            
            # Simulate Ctrl+V (paste)
            # This might not work on all devices/keyboards
            self.send_keyevent(279)  # KEYCODE_PASTE (if supported)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to paste text: {e}")
            return False

    def get_clipboard_text(self) -> str:
        """
        Get current clipboard content.
        
        Returns:
            str: Clipboard content or empty string if failed
        """
        try:
            # This requires a clipboard app or service
            result = self.execute_shell_command("am broadcast -a clipper.get", timeout=10)
            # Parsing would depend on the specific clipboard implementation
            return result.strip()
            
        except Exception as e:
            logger.error(f"Failed to get clipboard text: {e}")
            return ""

    def input_special_characters(self, text: str) -> bool:
        """
        Input text with special characters using Unicode input method.
        
        Args:
            text: Text containing special characters
            
        Returns:
            bool: True if successful
        """
        try:
            for char in text:
                if ord(char) > 127:  # Non-ASCII character
                    # Use Unicode input for special characters
                    unicode_value = ord(char)
                    # This method may not work on all devices
                    command = f"input text '\\u{unicode_value:04x}'"
                    self.execute_shell_command(command, timeout=5)
                else:
                    # Regular character
                    self.input_text(char, delay_between_chars=False)
                
                # Small delay between characters
                time.sleep(random.uniform(0.05, 0.1))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to input special characters: {e}")
            return False

    # ========== SCREENSHOT AND IMAGE PROCESSING METHODS ==========
    
    def take_screenshot(self, filename: str = None, format: str = "png") -> Optional[str]:
        """
        Capture a screenshot of the device screen.
        
        Args:
            filename: Custom filename (None for auto-generated)
            format: Image format ("png" or "jpg")
            
        Returns:
            Optional[str]: Path to saved screenshot or None if failed
        """
        try:
            # Generate filename if not provided
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.{format}"
            
            # Ensure screenshots directory exists
            self.screenshots_dir.mkdir(exist_ok=True)
            local_path = self.screenshots_dir / filename
            
            # Take screenshot on device
            device_screenshot_path = f"/sdcard/screenshot_temp.{format}"
            
            # Capture screenshot
            if format.lower() == "png":
                command = f"screencap -p {device_screenshot_path}"
            else:
                command = f"screencap {device_screenshot_path}"
            
            result = self.execute_shell_command(command, timeout=15)
            
            # Pull screenshot from device
            self.device.pull(device_screenshot_path, str(local_path))
            
            # Clean up temporary file on device
            self.execute_shell_command(f"rm {device_screenshot_path}", timeout=5)
            
            # Verify file was created and has content
            if local_path.exists() and local_path.stat().st_size > 0:
                logger.info(f"Screenshot saved: {local_path}")
                return str(local_path)
            else:
                raise Exception("Screenshot file was not created or is empty")
                
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None

    def take_screenshot_region(self, x: int, y: int, width: int, height: int, filename: str = None) -> Optional[str]:
        """
        Capture a screenshot of a specific region.
        
        Args:
            x: Left coordinate
            y: Top coordinate
            width: Region width
            height: Region height
            filename: Custom filename
            
        Returns:
            Optional[str]: Path to saved screenshot or None if failed
        """
        try:
            # First take a full screenshot
            full_screenshot = self.take_screenshot()
            if not full_screenshot:
                return None
            
            # Crop the image to the specified region
            from PIL import Image
            
            with Image.open(full_screenshot) as img:
                # Crop the region
                cropped = img.crop((x, y, x + width, y + height))
                
                # Generate filename if not provided
                if filename is None:
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    filename = f"screenshot_region_{timestamp}.png"
                
                # Save cropped image
                region_path = self.screenshots_dir / filename
                cropped.save(region_path)
                
                # Clean up full screenshot
                os.remove(full_screenshot)
                
                logger.info(f"Region screenshot saved: {region_path}")
                return str(region_path)
                
        except Exception as e:
            logger.error(f"Failed to take region screenshot: {e}")
            return None

    def take_multiple_screenshots(self, count: int, interval: float = 1.0, prefix: str = "multi") -> List[str]:
        """
        Take multiple screenshots with specified intervals.
        
        Args:
            count: Number of screenshots to take
            interval: Time interval between screenshots in seconds
            prefix: Filename prefix
            
        Returns:
            List[str]: List of screenshot file paths
        """
        screenshots = []
        
        try:
            for i in range(count):
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"{prefix}_{i+1:03d}_{timestamp}.png"
                
                screenshot_path = self.take_screenshot(filename)
                if screenshot_path:
                    screenshots.append(screenshot_path)
                    logger.debug(f"Screenshot {i+1}/{count} saved")
                else:
                    logger.warning(f"Failed to take screenshot {i+1}/{count}")
                
                # Wait before next screenshot (except for the last one)
                if i < count - 1:
                    time.sleep(interval)
            
            logger.info(f"Captured {len(screenshots)}/{count} screenshots")
            return screenshots
            
        except Exception as e:
            logger.error(f"Failed to take multiple screenshots: {e}")
            return screenshots

    def capture_screen_recording(self, duration: int = 10, filename: str = None, bitrate: str = "4M") -> Optional[str]:
        """
        Record screen video (requires Android 4.4+).
        
        Args:
            duration: Recording duration in seconds
            filename: Custom filename
            bitrate: Video bitrate (e.g., "4M", "8M")
            
        Returns:
            Optional[str]: Path to saved video or None if failed
        """
        try:
            # Generate filename if not provided
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screen_recording_{timestamp}.mp4"
            
            # Ensure screenshots directory exists
            self.screenshots_dir.mkdir(exist_ok=True)
            local_path = self.screenshots_dir / filename
            
            # Record on device
            device_video_path = f"/sdcard/screen_recording_temp.mp4"
            
            # Start screen recording
            command = f"screenrecord --time-limit {duration} --bit-rate {bitrate} {device_video_path}"
            logger.info(f"Starting screen recording for {duration} seconds...")
            
            result = self.execute_shell_command(command, timeout=duration + 10)
            
            # Pull video from device
            self.device.pull(device_video_path, str(local_path))
            
            # Clean up temporary file on device
            self.execute_shell_command(f"rm {device_video_path}", timeout=5)
            
            # Verify file was created
            if local_path.exists() and local_path.stat().st_size > 0:
                logger.info(f"Screen recording saved: {local_path}")
                return str(local_path)
            else:
                raise Exception("Screen recording file was not created or is empty")
                
        except Exception as e:
            logger.error(f"Failed to capture screen recording: {e}")
            return None

    def preprocess_screenshot_for_ocr(self, screenshot_path: str, output_path: str = None) -> Optional[str]:
        """
        Preprocess screenshot image for better OCR accuracy.
        
        Args:
            screenshot_path: Path to input screenshot
            output_path: Path for processed image (None for auto-generated)
            
        Returns:
            Optional[str]: Path to processed image or None if failed
        """
        try:
            import cv2
            import numpy as np
            
            if output_path is None:
                base_name = Path(screenshot_path).stem
                output_path = self.screenshots_dir / f"{base_name}_processed.png"
            
            # Load image
            img = cv2.imread(screenshot_path)
            if img is None:
                raise Exception(f"Could not load image: {screenshot_path}")
            
            # Convert to grayscale
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Apply adaptive thresholding for better text contrast
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            
            # Optional: Apply morphological operations to clean up the image
            kernel = np.ones((2, 2), np.uint8)
            processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
            
            # Save processed image
            cv2.imwrite(str(output_path), processed)
            
            logger.debug(f"Preprocessed image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to preprocess screenshot: {e}")
            return None

    def enhance_image_contrast(self, image_path: str, output_path: str = None, alpha: float = 1.5, beta: int = 30) -> Optional[str]:
        """
        Enhance image contrast and brightness for better OCR results.
        
        Args:
            image_path: Path to input image
            output_path: Path for enhanced image
            alpha: Contrast control (1.0-3.0)
            beta: Brightness control (0-100)
            
        Returns:
            Optional[str]: Path to enhanced image or None if failed
        """
        try:
            import cv2
            
            if output_path is None:
                base_name = Path(image_path).stem
                output_path = self.screenshots_dir / f"{base_name}_enhanced.png"
            
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                raise Exception(f"Could not load image: {image_path}")
            
            # Apply contrast and brightness enhancement
            enhanced = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
            
            # Save enhanced image
            cv2.imwrite(str(output_path), enhanced)
            
            logger.debug(f"Enhanced image saved: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"Failed to enhance image: {e}")
            return None

    def resize_image(self, image_path: str, width: int = None, height: int = None, 
                    scale_factor: float = None, output_path: str = None) -> Optional[str]:
        """
        Resize image for processing or storage optimization.
        
        Args:
            image_path: Path to input image
            width: Target width (None to maintain aspect ratio)
            height: Target height (None to maintain aspect ratio)
            scale_factor: Scale factor (e.g., 0.5 for half size)
            output_path: Path for resized image
            
        Returns:
            Optional[str]: Path to resized image or None if failed
        """
        try:
            from PIL import Image
            
            if output_path is None:
                base_name = Path(image_path).stem
                output_path = self.screenshots_dir / f"{base_name}_resized.png"
            
            with Image.open(image_path) as img:
                original_width, original_height = img.size
                
                if scale_factor:
                    new_width = int(original_width * scale_factor)
                    new_height = int(original_height * scale_factor)
                elif width and height:
                    new_width, new_height = width, height
                elif width:
                    new_height = int(original_height * (width / original_width))
                    new_width = width
                elif height:
                    new_width = int(original_width * (height / original_height))
                    new_height = height
                else:
                    raise Exception("Must specify width, height, or scale_factor")
                
                # Resize image
                resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                resized.save(output_path)
                
                logger.debug(f"Resized image saved: {output_path} ({new_width}x{new_height})")
                return str(output_path)
                
        except Exception as e:
            logger.error(f"Failed to resize image: {e}")
            return None

    def compare_screenshots(self, image1_path: str, image2_path: str, threshold: float = 0.95) -> bool:
        """
        Compare two screenshots to detect changes.
        
        Args:
            image1_path: Path to first image
            image2_path: Path to second image
            threshold: Similarity threshold (0.0-1.0)
            
        Returns:
            bool: True if images are similar (above threshold)
        """
        try:
            import cv2
            import numpy as np
            
            # Load images
            img1 = cv2.imread(image1_path, cv2.IMREAD_GRAYSCALE)
            img2 = cv2.imread(image2_path, cv2.IMREAD_GRAYSCALE)
            
            if img1 is None or img2 is None:
                raise Exception("Could not load one or both images")
            
            # Resize images to same size if different
            if img1.shape != img2.shape:
                img2 = cv2.resize(img2, (img1.shape[1], img1.shape[0]))
            
            # Calculate structural similarity
            from sklearn.metrics import mean_squared_error
            mse = mean_squared_error(img1.flatten(), img2.flatten())
            
            # Convert MSE to similarity score (0-1)
            max_mse = 255 * 255  # Maximum possible MSE for 8-bit images
            similarity = 1 - (mse / max_mse)
            
            logger.debug(f"Image similarity: {similarity:.3f}")
            return similarity >= threshold
            
        except Exception as e:
            logger.error(f"Failed to compare screenshots: {e}")
            return False

    def cleanup_old_screenshots(self, max_age_hours: int = 24, max_count: int = 100) -> int:
        """
        Clean up old screenshot files to save storage space.
        
        Args:
            max_age_hours: Delete files older than this many hours
            max_count: Keep only this many most recent files
            
        Returns:
            int: Number of files deleted
        """
        try:
            deleted_count = 0
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            # Get all screenshot files
            screenshot_files = []
            for pattern in ["*.png", "*.jpg", "*.jpeg", "*.mp4"]:
                screenshot_files.extend(self.screenshots_dir.glob(pattern))
            
            # Sort by modification time (newest first)
            screenshot_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Delete files based on age and count limits
            for i, file_path in enumerate(screenshot_files):
                file_age = current_time - file_path.stat().st_mtime
                
                # Delete if too old or beyond count limit
                if file_age > max_age_seconds or i >= max_count:
                    try:
                        file_path.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old screenshot: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {file_path}: {e}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old screenshot files")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup screenshots: {e}")
            return 0

    # ========== TOUCH EVENT SIMULATION METHODS ==========
    
    def tap(self, x: int, y: int, duration: int = None) -> bool:
        """
        Simulate a tap (touch) event at specified coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate  
            duration: Touch duration in milliseconds (None for instant tap)
            
        Returns:
            bool: True if tap successful
        """
        try:
            if duration is None:
                # Simple tap
                command = f"input tap {x} {y}"
            else:
                # Tap with duration using touchscreen events
                command = f"input touchscreen tap {x} {y}"
                
            result = self.execute_shell_command(command, timeout=10)
            
            # Add human-like delay after tap
            delay = random.uniform(0.1, 0.3)
            time.sleep(delay)
            
            logger.debug(f"Tap executed at ({x}, {y})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute tap at ({x}, {y}): {e}")
            return False

    def long_press(self, x: int, y: int, duration: int = 1000) -> bool:
        """
        Simulate a long press at specified coordinates.
        
        Args:
            x: X coordinate
            y: Y coordinate
            duration: Press duration in milliseconds
            
        Returns:
            bool: True if long press successful
        """
        try:
            # Use swipe with same start/end coordinates for long press
            command = f"input swipe {x} {y} {x} {y} {duration}"
            result = self.execute_shell_command(command, timeout=15)
            
            logger.debug(f"Long press executed at ({x}, {y}) for {duration}ms")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute long press at ({x}, {y}): {e}")
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """
        Simulate a swipe gesture from one point to another.
        
        Args:
            x1: Start X coordinate
            y1: Start Y coordinate
            x2: End X coordinate
            y2: End Y coordinate
            duration: Swipe duration in milliseconds
            
        Returns:
            bool: True if swipe successful
        """
        try:
            command = f"input swipe {x1} {y1} {x2} {y2} {duration}"
            result = self.execute_shell_command(command, timeout=10)
            
            # Add human-like delay after swipe
            delay = random.uniform(0.2, 0.5)
            time.sleep(delay)
            
            logger.debug(f"Swipe executed from ({x1}, {y1}) to ({x2}, {y2})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute swipe: {e}")
            return False

    def scroll_down(self, x: int = None, y: int = None, distance: int = 500) -> bool:
        """
        Scroll down on the screen.
        
        Args:
            x: X coordinate (center of screen if None)
            y: Y coordinate (center of screen if None)
            distance: Scroll distance in pixels
            
        Returns:
            bool: True if scroll successful
        """
        try:
            # Get screen dimensions if coordinates not provided
            if x is None or y is None:
                screen_size = self.get_screen_size()
                if not screen_size:
                    # Default fallback coordinates
                    x = x or 540
                    y = y or 960
                else:
                    x = x or screen_size[0] // 2
                    y = y or screen_size[1] // 2
            
            # Scroll down: swipe from bottom to top
            start_y = y + distance // 2
            end_y = y - distance // 2
            
            return self.swipe(x, start_y, x, end_y, duration=400)
            
        except Exception as e:
            logger.error(f"Failed to scroll down: {e}")
            return False

    def scroll_up(self, x: int = None, y: int = None, distance: int = 500) -> bool:
        """
        Scroll up on the screen.
        
        Args:
            x: X coordinate (center of screen if None)
            y: Y coordinate (center of screen if None)
            distance: Scroll distance in pixels
            
        Returns:
            bool: True if scroll successful
        """
        try:
            # Get screen dimensions if coordinates not provided
            if x is None or y is None:
                screen_size = self.get_screen_size()
                if not screen_size:
                    # Default fallback coordinates
                    x = x or 540
                    y = y or 960
                else:
                    x = x or screen_size[0] // 2
                    y = y or screen_size[1] // 2
            
            # Scroll up: swipe from top to bottom
            start_y = y - distance // 2
            end_y = y + distance // 2
            
            return self.swipe(x, start_y, x, end_y, duration=400)
            
        except Exception as e:
            logger.error(f"Failed to scroll up: {e}")
            return False

    def swipe_left(self, y: int = None, distance: int = 400) -> bool:
        """
        Swipe left on the screen.
        
        Args:
            y: Y coordinate (center of screen if None)
            distance: Swipe distance in pixels
            
        Returns:
            bool: True if swipe successful
        """
        try:
            screen_size = self.get_screen_size()
            if not screen_size:
                y = y or 960
                center_x = 540
            else:
                y = y or screen_size[1] // 2
                center_x = screen_size[0] // 2
            
            start_x = center_x + distance // 2
            end_x = center_x - distance // 2
            
            return self.swipe(start_x, y, end_x, y, duration=300)
            
        except Exception as e:
            logger.error(f"Failed to swipe left: {e}")
            return False

    def swipe_right(self, y: int = None, distance: int = 400) -> bool:
        """
        Swipe right on the screen.
        
        Args:
            y: Y coordinate (center of screen if None)
            distance: Swipe distance in pixels
            
        Returns:
            bool: True if swipe successful
        """
        try:
            screen_size = self.get_screen_size()
            if not screen_size:
                y = y or 960
                center_x = 540
            else:
                y = y or screen_size[1] // 2
                center_x = screen_size[0] // 2
            
            start_x = center_x - distance // 2
            end_x = center_x + distance // 2
            
            return self.swipe(start_x, y, end_x, y, duration=300)
            
        except Exception as e:
            logger.error(f"Failed to swipe right: {e}")
            return False

    def drag_and_drop(self, x1: int, y1: int, x2: int, y2: int, duration: int = 1000) -> bool:
        """
        Simulate a drag and drop operation.
        
        Args:
            x1: Start X coordinate
            y1: Start Y coordinate
            x2: End X coordinate
            y2: End Y coordinate
            duration: Drag duration in milliseconds
            
        Returns:
            bool: True if drag and drop successful
        """
        try:
            # Use longer duration for drag and drop
            command = f"input swipe {x1} {y1} {x2} {y2} {duration}"
            result = self.execute_shell_command(command, timeout=15)
            
            logger.debug(f"Drag and drop from ({x1}, {y1}) to ({x2}, {y2})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute drag and drop: {e}")
            return False

    def pinch_zoom_in(self, center_x: int, center_y: int, distance: int = 200) -> bool:
        """
        Simulate pinch zoom in gesture (two finger zoom).
        
        Args:
            center_x: Center X coordinate
            center_y: Center Y coordinate
            distance: Distance between fingers
            
        Returns:
            bool: True if pinch zoom successful
        """
        try:
            # Calculate start and end positions for two fingers
            finger1_start_x = center_x - distance // 4
            finger1_start_y = center_y
            finger1_end_x = center_x - distance // 2
            finger1_end_y = center_y
            
            finger2_start_x = center_x + distance // 4
            finger2_start_y = center_y
            finger2_end_x = center_x + distance // 2
            finger2_end_y = center_y
            
            # Execute pinch zoom using multiple swipes (limited by ADB input capabilities)
            success1 = self.swipe(finger1_start_x, finger1_start_y, finger1_end_x, finger1_end_y, 500)
            time.sleep(0.1)
            success2 = self.swipe(finger2_start_x, finger2_start_y, finger2_end_x, finger2_end_y, 500)
            
            logger.debug(f"Pinch zoom in at ({center_x}, {center_y})")
            return success1 and success2
            
        except Exception as e:
            logger.error(f"Failed to execute pinch zoom in: {e}")
            return False

    def pinch_zoom_out(self, center_x: int, center_y: int, distance: int = 200) -> bool:
        """
        Simulate pinch zoom out gesture (two finger zoom).
        
        Args:
            center_x: Center X coordinate
            center_y: Center Y coordinate
            distance: Distance between fingers
            
        Returns:
            bool: True if pinch zoom successful
        """
        try:
            # Calculate start and end positions for two fingers (reverse of zoom in)
            finger1_start_x = center_x - distance // 2
            finger1_start_y = center_y
            finger1_end_x = center_x - distance // 4
            finger1_end_y = center_y
            
            finger2_start_x = center_x + distance // 2
            finger2_start_y = center_y
            finger2_end_x = center_x + distance // 4
            finger2_end_y = center_y
            
            # Execute pinch zoom using multiple swipes
            success1 = self.swipe(finger1_start_x, finger1_start_y, finger1_end_x, finger1_end_y, 500)
            time.sleep(0.1)
            success2 = self.swipe(finger2_start_x, finger2_start_y, finger2_end_x, finger2_end_y, 500)
            
            logger.debug(f"Pinch zoom out at ({center_x}, {center_y})")
            return success1 and success2
            
        except Exception as e:
            logger.error(f"Failed to execute pinch zoom out: {e}")
            return False

    def get_screen_size(self) -> Optional[Tuple[int, int]]:
        """
        Get the screen size of the device.
        
        Returns:
            Optional[Tuple[int, int]]: (width, height) or None if failed
        """
        try:
            result = self.execute_shell_command("wm size", timeout=10)
            
            # Parse output like "Physical size: 1080x1920"
            for line in result.split('\n'):
                if 'size:' in line.lower():
                    size_part = line.split(':')[-1].strip()
                    if 'x' in size_part:
                        width, height = map(int, size_part.split('x'))
                        return (width, height)
            
            # Fallback: try dumpsys
            result = self.execute_shell_command("dumpsys display | grep mBaseDisplayInfo", timeout=10)
            # This is more complex parsing, simplified for now
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get screen size: {e}")
            return None

    def add_human_like_delay(self, min_delay: float = 0.5, max_delay: float = 2.0) -> None:
        """
        Add a human-like delay to simulate natural interaction patterns.
        
        Args:
            min_delay: Minimum delay in seconds
            max_delay: Maximum delay in seconds
        """
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
        logger.debug(f"Human-like delay: {delay:.2f}s")

    def simulate_natural_touch_sequence(self, actions: List[Dict]) -> bool:
        """
        Execute a sequence of touch actions with natural human-like timing.
        
        Args:
            actions: List of action dictionaries with keys like:
                    {'action': 'tap', 'x': 100, 'y': 200}
                    {'action': 'swipe', 'x1': 100, 'y1': 200, 'x2': 300, 'y2': 400}
                    {'action': 'delay', 'duration': 1.5}
                    
        Returns:
            bool: True if all actions successful
        """
        try:
            for action in actions:
                action_type = action.get('action')
                
                if action_type == 'tap':
                    success = self.tap(action['x'], action['y'])
                elif action_type == 'long_press':
                    duration = action.get('duration', 1000)
                    success = self.long_press(action['x'], action['y'], duration)
                elif action_type == 'swipe':
                    duration = action.get('duration', 300)
                    success = self.swipe(action['x1'], action['y1'], action['x2'], action['y2'], duration)
                elif action_type == 'delay':
                    time.sleep(action.get('duration', 1.0))
                    success = True
                elif action_type == 'human_delay':
                    min_delay = action.get('min', 0.5)
                    max_delay = action.get('max', 2.0)
                    self.add_human_like_delay(min_delay, max_delay)
                    success = True
                else:
                    logger.warning(f"Unknown action type: {action_type}")
                    success = True
                
                if not success and action_type != 'delay':
                    logger.error(f"Failed to execute action: {action}")
                    return False
                    
                # Add small random delay between actions
                if action_type != 'delay' and action_type != 'human_delay':
                    time.sleep(random.uniform(0.1, 0.5))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute touch sequence: {e}")
            return False

    def disconnect(self) -> None:
        """Safely disconnect from the device."""
        try:
            if self.device and self.is_connected:
                self.device.close()
                self.is_connected = False
                logger.info("Device disconnected successfully")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")

    def reconnect(self, max_retries: int = 3) -> bool:
        """
        Attempt to reconnect to the device.
        
        Args:
            max_retries: Maximum number of reconnection attempts
            
        Returns:
            bool: True if reconnection successful
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"Reconnection attempt {attempt + 1}/{max_retries}")
                self.disconnect()
                time.sleep(2)  # Wait before retry
                return self.connect_device()
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")
                
        logger.error("All reconnection attempts failed")
        return False

    def is_device_ready(self) -> bool:
        """
        Check if device is ready for operations.
        
        Returns:
            bool: True if device is connected and responsive
        """
        if not self.is_connected or not self.device:
            return False
            
        try:
            # Check if device is responsive
            boot_complete = self.device.shell("getprop sys.boot_completed", timeout_s=10)
            return boot_complete.strip() == "1"
        except Exception as e:
            logger.error(f"Device readiness check failed: {e}")
            return False

    def get_connected_devices(self) -> List[str]:
        """
        Get list of connected devices (placeholder for future implementation).
        
        Returns:
            List[str]: List of connected device IDs
        """
        # This would require adb server functionality
        # For now, return current device if connected
        if self.is_connected and self.device_info.get('serial'):
            return [self.device_info['serial']]
        return []

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.disconnect()

    def __del__(self):
        """Destructor to ensure cleanup."""
        try:
            self.disconnect()
        except:
            pass 