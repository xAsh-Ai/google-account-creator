"""
Account Activity Module for Google Account Creator

This module implements post-creation activities to improve account survival rates
by simulating natural human behavior on Google services.

Features:
- YouTube video watching with natural patterns
- Gmail sending and interaction
- Profile updating and customization
- Human-like browsing patterns with randomized delays
- Comprehensive activity logging
- Anti-detection measures
"""

import time
import random
import json
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import undetected_chromedriver as uc

from core.logger import get_logger, LoggingContext

logger = get_logger("AccountActivity")

class ActivityType(Enum):
    """Types of activities that can be performed"""
    YOUTUBE_WATCH = "youtube_watch"
    GMAIL_SEND = "gmail_send"
    PROFILE_UPDATE = "profile_update"
    SEARCH_QUERY = "search_query"
    GENERAL_BROWSING = "general_browsing"

class ActivityStatus(Enum):
    """Status of activity execution"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class AccountInfo:
    """Information about the Google account"""
    email: str
    password: str
    recovery_email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[str] = None
    created_at: Optional[datetime] = None

@dataclass
class ActivityConfig:
    """Configuration for activity execution"""
    max_youtube_videos: int = 5
    min_watch_duration: int = 30  # seconds
    max_watch_duration: int = 180  # seconds
    gmail_recipients: List[str] = field(default_factory=list)
    profile_update_fields: List[str] = field(default_factory=lambda: ["about", "location", "work"])
    delay_between_activities: Tuple[int, int] = (30, 120)  # min, max seconds
    use_random_delays: bool = True
    simulate_human_behavior: bool = True
    max_activity_duration: int = 3600  # max 1 hour of activities

@dataclass
class ActivityResult:
    """Result of an activity execution"""
    activity_type: ActivityType
    status: ActivityStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    success_metrics: Dict[str, Any] = field(default_factory=dict)

class HumanBehaviorSimulator:
    """Simulates human-like behavior patterns"""
    
    def __init__(self):
        self.typing_speeds = {
            'slow': (0.1, 0.3),
            'normal': (0.05, 0.15),
            'fast': (0.02, 0.08)
        }
        self.mouse_movement_patterns = [
            'linear', 'curved', 'stepped', 'jerky'
        ]
        
    def human_type(self, element, text: str, speed: str = 'normal') -> None:
        """Type text with human-like patterns"""
        min_delay, max_delay = self.typing_speeds[speed]
        
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(min_delay, max_delay))
            
            # Occasionally pause longer (thinking time)
            if random.random() < 0.1:
                time.sleep(random.uniform(0.5, 2.0))
    
    def human_scroll(self, driver, direction: str = 'down', distance: int = 3) -> None:
        """Scroll with human-like patterns"""
        body = driver.find_element(By.TAG_NAME, 'body')
        
        for _ in range(distance):
            if direction == 'down':
                body.send_keys(Keys.PAGE_DOWN)
            else:
                body.send_keys(Keys.PAGE_UP)
            
            # Random pause between scrolls
            time.sleep(random.uniform(0.5, 2.0))
    
    def random_mouse_movement(self, driver) -> None:
        """Perform random mouse movements to simulate human behavior"""
        try:
            actions = ActionChains(driver)
            
            # Get window size
            window_size = driver.get_window_size()
            width, height = window_size['width'], window_size['height']
            
            # Generate random coordinates
            x = random.randint(100, width - 100)
            y = random.randint(100, height - 100)
            
            # Move to random location
            actions.move_by_offset(x, y).perform()
            
            # Small random pause
            time.sleep(random.uniform(0.1, 0.5))
            
        except Exception as e:
            logger.debug(f"Mouse movement simulation failed: {e}")
    
    def reading_pause(self, min_seconds: int = 2, max_seconds: int = 10) -> None:
        """Simulate reading/viewing pause"""
        pause_time = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Simulating reading pause for {pause_time:.1f} seconds")
        time.sleep(pause_time)

class YouTubeActivityManager:
    """Manages YouTube-related activities"""
    
    def __init__(self, driver: webdriver.Chrome, behavior_simulator: HumanBehaviorSimulator):
        self.driver = driver
        self.behavior_simulator = behavior_simulator
        self.wait = WebDriverWait(driver, 10)
        
        # Popular video categories and search terms for natural behavior
        self.search_terms = [
            "music", "tutorials", "funny videos", "news", "technology",
            "cooking", "travel", "gaming", "sports", "movies", "education",
            "science", "animals", "fitness", "art", "photography"
        ]
        
        self.video_categories = [
            "trending", "music", "gaming", "news", "movies", "sports"
        ]
    
    def navigate_to_youtube(self) -> bool:
        """Navigate to YouTube homepage"""
        try:
            with LoggingContext(logger, activity="youtube_navigation"):
                logger.info("Navigating to YouTube")
                self.driver.get("https://www.youtube.com")
                
                # Wait for page to load
                self.wait.until(EC.presence_of_element_located((By.ID, "content")))
                
                # Simulate looking at the page
                self.behavior_simulator.reading_pause(2, 5)
                
                logger.info("Successfully navigated to YouTube")
                return True
                
        except Exception as e:
            logger.error(f"Failed to navigate to YouTube: {e}")
            return False
    
    def search_videos(self, query: str) -> bool:
        """Search for videos with given query"""
        try:
            with LoggingContext(logger, activity="youtube_search", query=query):
                logger.info(f"Searching YouTube for: {query}")
                
                # Find search box
                search_box = self.wait.until(
                    EC.element_to_be_clickable((By.NAME, "search_query"))
                )
                
                # Clear and type search query
                search_box.clear()
                self.behavior_simulator.human_type(search_box, query)
                
                # Submit search
                search_box.send_keys(Keys.RETURN)
                
                # Wait for results
                self.wait.until(
                    EC.presence_of_element_located((By.ID, "contents"))
                )
                
                # Simulate looking at search results
                self.behavior_simulator.reading_pause(3, 7)
                
                logger.info(f"Search completed for: {query}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to search for '{query}': {e}")
            return False
    
    def find_suitable_videos(self, max_videos: int = 5) -> List[Dict[str, Any]]:
        """Find suitable videos to watch"""
        videos = []
        
        try:
            # Find video elements
            video_elements = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "ytd-video-renderer, ytd-compact-video-renderer"
            )[:max_videos * 2]  # Get more than needed for filtering
            
            for element in video_elements:
                try:
                    # Extract video information
                    title_element = element.find_element(By.CSS_SELECTOR, "a#video-title")
                    title = title_element.get_attribute("title") or title_element.text
                    url = title_element.get_attribute("href")
                    
                    # Try to get duration (not always available)
                    duration = None
                    try:
                        duration_element = element.find_element(By.CSS_SELECTOR, ".ytd-thumbnail-overlay-time-status-renderer")
                        duration = duration_element.text
                    except NoSuchElementException:
                        pass
                    
                    # Try to get view count
                    views = None
                    try:
                        views_element = element.find_element(By.CSS_SELECTOR, ".inline-metadata-item")
                        views = views_element.text
                    except NoSuchElementException:
                        pass
                    
                    if url and title:
                        videos.append({
                            'title': title,
                            'url': url,
                            'duration': duration,
                            'views': views,
                            'element': element
                        })
                        
                        if len(videos) >= max_videos:
                            break
                            
                except Exception as e:
                    logger.debug(f"Error extracting video info: {e}")
                    continue
            
            logger.info(f"Found {len(videos)} suitable videos")
            return videos
            
        except Exception as e:
            logger.error(f"Failed to find videos: {e}")
            return []
    
    def watch_video(self, video: Dict[str, Any], watch_duration: int) -> ActivityResult:
        """Watch a specific video for given duration"""
        result = ActivityResult(
            activity_type=ActivityType.YOUTUBE_WATCH,
            status=ActivityStatus.IN_PROGRESS,
            start_time=datetime.now()
        )
        
        try:
            with LoggingContext(logger, activity="youtube_watch", video_title=video['title']):
                logger.info(f"Starting to watch video: {video['title']}")
                
                # Click on video
                video['element'].click()
                
                # Wait for video player to load
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "video"))
                )
                
                # Random delay before interacting
                time.sleep(random.uniform(1, 3))
                
                # Simulate watching behavior
                watch_start = time.time()
                watch_end = watch_start + watch_duration
                
                interaction_count = 0
                while time.time() < watch_end:
                    remaining_time = watch_end - time.time()
                    
                    # Perform random interactions
                    if random.random() < 0.3 and interaction_count < 3:
                        self._perform_random_video_interaction()
                        interaction_count += 1
                    
                    # Random scroll or mouse movement
                    if random.random() < 0.2:
                        if random.random() < 0.5:
                            self.behavior_simulator.human_scroll(self.driver)
                        else:
                            self.behavior_simulator.random_mouse_movement(self.driver)
                    
                    # Sleep for a bit
                    sleep_time = min(random.uniform(5, 15), remaining_time)
                    time.sleep(sleep_time)
                
                actual_duration = time.time() - watch_start
                
                result.status = ActivityStatus.COMPLETED
                result.end_time = datetime.now()
                result.duration = actual_duration
                result.details = {
                    'video_title': video['title'],
                    'video_url': video['url'],
                    'planned_duration': watch_duration,
                    'actual_duration': actual_duration,
                    'interactions_performed': interaction_count
                }
                result.success_metrics = {
                    'completion_rate': min(actual_duration / watch_duration, 1.0),
                    'interactions': interaction_count
                }
                
                logger.info(f"Completed watching video for {actual_duration:.1f} seconds")
                
        except Exception as e:
            result.status = ActivityStatus.FAILED
            result.end_time = datetime.now()
            result.error_message = str(e)
            logger.error(f"Failed to watch video: {e}")
        
        return result
    
    def _perform_random_video_interaction(self) -> None:
        """Perform random interactions with video player"""
        try:
            interactions = ['like', 'expand_description', 'scroll_comments']
            interaction = random.choice(interactions)
            
            if interaction == 'like':
                self._try_like_video()
            elif interaction == 'expand_description':
                self._try_expand_description()
            elif interaction == 'scroll_comments':
                self._try_scroll_comments()
                
            logger.debug(f"Performed video interaction: {interaction}")
            
        except Exception as e:
            logger.debug(f"Video interaction failed: {e}")
    
    def _try_like_video(self) -> None:
        """Try to like the video"""
        try:
            like_button = self.driver.find_element(
                By.CSS_SELECTOR, 
                "button[aria-label*='like'], yt-icon-button#segmented-like-button"
            )
            if like_button.is_enabled():
                like_button.click()
                time.sleep(random.uniform(0.5, 1.5))
        except Exception:
            pass
    
    def _try_expand_description(self) -> None:
        """Try to expand video description"""
        try:
            show_more = self.driver.find_element(
                By.CSS_SELECTOR,
                "tp-yt-paper-button#expand"
            )
            if show_more.is_displayed():
                show_more.click()
                time.sleep(random.uniform(1, 3))
        except Exception:
            pass
    
    def _try_scroll_comments(self) -> None:
        """Try to scroll to and view comments"""
        try:
            # Scroll down to comments section
            self.behavior_simulator.human_scroll(self.driver, 'down', 2)
            
            # Look for comments
            comments = self.driver.find_elements(
                By.CSS_SELECTOR,
                "ytd-comment-thread-renderer"
            )
            
            if comments:
                # Simulate reading some comments
                self.behavior_simulator.reading_pause(2, 5)
                
        except Exception:
            pass
    
    def execute_youtube_activity(self, config: ActivityConfig) -> List[ActivityResult]:
        """Execute complete YouTube activity session"""
        results = []
        
        try:
            with LoggingContext(logger, activity="youtube_session"):
                logger.info("Starting YouTube activity session")
                
                # Navigate to YouTube
                if not self.navigate_to_youtube():
                    return results
                
                # Perform multiple video watches
                videos_watched = 0
                max_videos = min(config.max_youtube_videos, 5)
                
                while videos_watched < max_videos:
                    try:
                        # Choose search term or browse trending
                        if random.random() < 0.7:  # 70% search, 30% browse
                            search_term = random.choice(self.search_terms)
                            if not self.search_videos(search_term):
                                continue
                        else:
                            # Browse trending or homepage
                            self.navigate_to_youtube()
                        
                        # Find videos
                        videos = self.find_suitable_videos(3)
                        if not videos:
                            logger.warning("No suitable videos found")
                            break
                        
                        # Select random video
                        video = random.choice(videos)
                        
                        # Calculate watch duration
                        watch_duration = random.randint(
                            config.min_watch_duration,
                            config.max_watch_duration
                        )
                        
                        # Watch video
                        result = self.watch_video(video, watch_duration)
                        results.append(result)
                        
                        videos_watched += 1
                        
                        # Break between videos
                        if videos_watched < max_videos:
                            delay = random.randint(*config.delay_between_activities)
                            logger.info(f"Waiting {delay} seconds before next video")
                            time.sleep(delay)
                            
                    except Exception as e:
                        logger.error(f"Error in video watching loop: {e}")
                        break
                
                logger.info(f"YouTube session completed. Watched {videos_watched} videos")
                
        except Exception as e:
            logger.error(f"YouTube activity session failed: {e}")
        
        return results

class GmailActivityManager:
    """Manages Gmail-related activities"""
    
    def __init__(self, driver: webdriver.Chrome, behavior_simulator: HumanBehaviorSimulator):
        self.driver = driver
        self.behavior_simulator = behavior_simulator
        self.wait = WebDriverWait(driver, 15)
        
        # Sample email content for natural communication
        self.email_subjects = [
            "Hello!", "Quick question", "Follow up", "Thanks!", "Update",
            "Meeting notes", "Project status", "Reminder", "Good news",
            "Schedule change", "Documents", "Information request"
        ]
        
        self.email_templates = [
            "Hi there!\n\nHope you're doing well. Just wanted to reach out and say hello.\n\nBest regards",
            "Hello!\n\nI wanted to follow up on our previous conversation. Let me know if you have any questions.\n\nThanks!",
            "Hi!\n\nJust a quick note to touch base. Hope everything is going well on your end.\n\nBest",
            "Hello!\n\nThank you for your help with the recent project. Really appreciate it!\n\nBest regards",
            "Hi there!\n\nI wanted to share some quick updates. Let me know your thoughts when you get a chance.\n\nThanks!"
        ]
    
    def navigate_to_gmail(self) -> bool:
        """Navigate to Gmail"""
        try:
            with LoggingContext(logger, activity="gmail_navigation"):
                logger.info("Navigating to Gmail")
                self.driver.get("https://mail.google.com")
                
                # Wait for Gmail interface to load
                self.wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-tooltip='Compose']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div[role='button'][data-tooltip='Compose']")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".T-I-KE"))  # Compose button
                    )
                )
                
                # Simulate looking at Gmail interface
                self.behavior_simulator.reading_pause(2, 5)
                
                logger.info("Successfully navigated to Gmail")
                return True
                
        except Exception as e:
            logger.error(f"Failed to navigate to Gmail: {e}")
            return False
    
    def compose_and_send_email(self, recipient: str, subject: str = None, body: str = None) -> ActivityResult:
        """Compose and send an email"""
        result = ActivityResult(
            activity_type=ActivityType.GMAIL_SEND,
            status=ActivityStatus.IN_PROGRESS,
            start_time=datetime.now()
        )
        
        try:
            with LoggingContext(logger, activity="gmail_compose", recipient=recipient):
                logger.info(f"Composing email to {recipient}")
                
                # Click compose button
                compose_selectors = [
                    "[data-tooltip='Compose']",
                    "div[role='button'][data-tooltip='Compose']",
                    ".T-I-KE",
                    "div[gh='cm']"
                ]
                
                compose_button = None
                for selector in compose_selectors:
                    try:
                        compose_button = self.wait.until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        break
                    except TimeoutException:
                        continue
                
                if not compose_button:
                    raise Exception("Could not find compose button")
                
                compose_button.click()
                
                # Wait for compose window
                time.sleep(random.uniform(1, 3))
                
                # Fill recipient
                to_field = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='to'], textarea[name='to'], div[name='to']"))
                )
                self.behavior_simulator.human_type(to_field, recipient)
                
                # Generate or use provided subject
                if not subject:
                    subject = random.choice(self.email_subjects)
                
                # Fill subject
                subject_field = self.driver.find_element(By.CSS_SELECTOR, "input[name='subjectbox'], input[placeholder*='Subject']")
                self.behavior_simulator.human_type(subject_field, subject)
                
                # Generate or use provided body
                if not body:
                    body = random.choice(self.email_templates)
                
                # Fill body
                body_field = self.driver.find_element(
                    By.CSS_SELECTOR, 
                    "div[role='textbox'], div[aria-label*='message body'], div[contenteditable='true']"
                )
                body_field.click()
                time.sleep(random.uniform(0.5, 1.5))
                self.behavior_simulator.human_type(body_field, body, speed='normal')
                
                # Simulate review time
                self.behavior_simulator.reading_pause(3, 8)
                
                # Send email
                send_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "div[role='button'][data-tooltip*='Send'], div[data-tooltip*='Send'], .T-I-KE"
                )
                send_button.click()
                
                # Wait for send confirmation
                time.sleep(random.uniform(2, 4))
                
                result.status = ActivityStatus.COMPLETED
                result.end_time = datetime.now()
                result.duration = (result.end_time - result.start_time).total_seconds()
                result.details = {
                    'recipient': recipient,
                    'subject': subject,
                    'body_length': len(body),
                    'sent_at': result.end_time.isoformat()
                }
                result.success_metrics = {
                    'email_sent': True,
                    'fields_filled': 3
                }
                
                logger.info(f"Successfully sent email to {recipient}")
                
        except Exception as e:
            result.status = ActivityStatus.FAILED
            result.end_time = datetime.now()
            result.error_message = str(e)
            logger.error(f"Failed to send email to {recipient}: {e}")
        
        return result
    
    def read_recent_emails(self, count: int = 3) -> ActivityResult:
        """Read recent emails to simulate natural Gmail usage"""
        result = ActivityResult(
            activity_type=ActivityType.GMAIL_SEND,  # Using as general Gmail activity
            status=ActivityStatus.IN_PROGRESS,
            start_time=datetime.now()
        )
        
        try:
            with LoggingContext(logger, activity="gmail_read"):
                logger.info(f"Reading recent emails")
                
                # Find email list
                email_elements = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    "tr.zA, div[role='listitem']"
                )[:count]
                
                emails_read = 0
                for email_element in email_elements:
                    try:
                        # Click to open email
                        email_element.click()
                        
                        # Simulate reading time
                        self.behavior_simulator.reading_pause(5, 15)
                        
                        # Go back to inbox
                        back_button = self.driver.find_element(
                            By.CSS_SELECTOR,
                            "div[data-tooltip='Back to inbox'], div[aria-label*='Back']"
                        )
                        back_button.click()
                        
                        emails_read += 1
                        time.sleep(random.uniform(1, 3))
                        
                    except Exception as e:
                        logger.debug(f"Error reading email: {e}")
                        continue
                
                result.status = ActivityStatus.COMPLETED
                result.end_time = datetime.now()
                result.duration = (result.end_time - result.start_time).total_seconds()
                result.details = {
                    'emails_read': emails_read,
                    'target_count': count
                }
                result.success_metrics = {
                    'emails_read': emails_read,
                    'completion_rate': emails_read / count if count > 0 else 0
                }
                
                logger.info(f"Read {emails_read} emails")
                
        except Exception as e:
            result.status = ActivityStatus.FAILED
            result.end_time = datetime.now()
            result.error_message = str(e)
            logger.error(f"Failed to read emails: {e}")
        
        return result 

class ProfileActivityManager:
    """Manages Google Profile-related activities"""
    
    def __init__(self, driver: webdriver.Chrome, behavior_simulator: HumanBehaviorSimulator):
        self.driver = driver
        self.behavior_simulator = behavior_simulator
        self.wait = WebDriverWait(driver, 15)
        
        # Sample profile data for updates
        self.about_texts = [
            "Passionate about technology and learning new things.",
            "Love exploring new places and meeting new people.",
            "Interested in science, art, and innovation.",
            "Enthusiastic about making a positive impact.",
            "Always curious and eager to learn something new."
        ]
        
        self.work_info = [
            "Software Engineer", "Marketing Specialist", "Data Analyst",
            "Graphic Designer", "Project Manager", "Consultant",
            "Teacher", "Researcher", "Freelancer", "Entrepreneur"
        ]
        
        self.locations = [
            "New York, NY", "Los Angeles, CA", "Chicago, IL", "Houston, TX",
            "Phoenix, AZ", "Philadelphia, PA", "San Antonio, TX", "San Diego, CA",
            "Dallas, TX", "San Jose, CA", "Austin, TX", "Jacksonville, FL"
        ]
    
    def navigate_to_profile(self) -> bool:
        """Navigate to Google account profile page"""
        try:
            with LoggingContext(logger, activity="profile_navigation"):
                logger.info("Navigating to Google profile")
                self.driver.get("https://myaccount.google.com/profile")
                
                # Wait for profile page to load
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-g-menu-item='profile']"))
                )
                
                # Simulate looking at profile
                self.behavior_simulator.reading_pause(3, 7)
                
                logger.info("Successfully navigated to profile")
                return True
                
        except Exception as e:
            logger.error(f"Failed to navigate to profile: {e}")
            return False
    
    def update_about_section(self, about_text: str = None) -> ActivityResult:
        """Update the about section of the profile"""
        result = ActivityResult(
            activity_type=ActivityType.PROFILE_UPDATE,
            status=ActivityStatus.IN_PROGRESS,
            start_time=datetime.now()
        )
        
        try:
            with LoggingContext(logger, activity="profile_about_update"):
                if not about_text:
                    about_text = random.choice(self.about_texts)
                
                logger.info("Updating profile about section")
                
                # Find and click edit button for about section
                edit_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label*='Edit'], .edit-button"))
                )
                edit_button.click()
                
                # Find about text field
                about_field = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea, input[type='text']"))
                )
                
                # Clear and update
                about_field.clear()
                self.behavior_simulator.human_type(about_field, about_text)
                
                # Save changes
                save_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "button[type='submit'], button[aria-label*='Save'], .save-button"
                )
                save_button.click()
                
                time.sleep(random.uniform(2, 4))
                
                result.status = ActivityStatus.COMPLETED
                result.end_time = datetime.now()
                result.duration = (result.end_time - result.start_time).total_seconds()
                result.details = {
                    'field': 'about',
                    'content': about_text,
                    'content_length': len(about_text)
                }
                result.success_metrics = {
                    'field_updated': True
                }
                
                logger.info("Successfully updated about section")
                
        except Exception as e:
            result.status = ActivityStatus.FAILED
            result.end_time = datetime.now()
            result.error_message = str(e)
            logger.error(f"Failed to update about section: {e}")
        
        return result

class MainAccountActivityManager:
    """Main manager that orchestrates all account activities"""
    
    def __init__(self, config: ActivityConfig):
        self.config = config
        self.driver = None
        self.behavior_simulator = HumanBehaviorSimulator()
        self.youtube_manager = None
        self.gmail_manager = None
        self.profile_manager = None
        
        # Activity tracking
        self.session_start_time = None
        self.total_activities_performed = 0
        self.activity_results: List[ActivityResult] = []
    
    def _setup_driver(self) -> bool:
        """Setup and configure the Chrome driver"""
        try:
            logger.info("Setting up Chrome driver")
            
            # Chrome options for stealth browsing
            options = uc.ChromeOptions()
            
            # Basic stealth options
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            
            # Performance and stability options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--remote-debugging-port=9222")
            
            # User agent and language
            options.add_argument("--lang=en-US")
            options.add_experimental_option("prefs", {
                "profile.default_content_setting_values.notifications": 2,
                "profile.managed_default_content_settings.images": 2
            })
            
            # Create driver
            self.driver = uc.Chrome(options=options)
            
            # Set window size
            self.driver.set_window_size(1366, 768)
            
            # Execute stealth script
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
            """)
            
            # Initialize activity managers
            self.youtube_manager = YouTubeActivityManager(self.driver, self.behavior_simulator)
            self.gmail_manager = GmailActivityManager(self.driver, self.behavior_simulator)
            self.profile_manager = ProfileActivityManager(self.driver, self.behavior_simulator)
            
            logger.info("Chrome driver setup completed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            return False
    
    def _cleanup_driver(self) -> None:
        """Clean up the Chrome driver"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                logger.info("Driver cleanup completed")
        except Exception as e:
            logger.error(f"Error during driver cleanup: {e}")
    
    def login_to_google(self, account: AccountInfo) -> bool:
        """Login to Google account"""
        try:
            with LoggingContext(logger, activity="google_login", email=account.email):
                logger.info(f"Logging into Google account: {account.email}")
                
                # Navigate to Google login
                self.driver.get("https://accounts.google.com/signin")
                
                wait = WebDriverWait(self.driver, 15)
                
                # Enter email
                email_field = wait.until(
                    EC.element_to_be_clickable((By.ID, "identifierId"))
                )
                self.behavior_simulator.human_type(email_field, account.email)
                
                # Click next
                next_button = self.driver.find_element(By.ID, "identifierNext")
                next_button.click()
                
                # Enter password
                password_field = wait.until(
                    EC.element_to_be_clickable((By.NAME, "password"))
                )
                self.behavior_simulator.human_type(password_field, account.password)
                
                # Click next
                password_next = self.driver.find_element(By.ID, "passwordNext")
                password_next.click()
                
                # Wait for login completion
                wait.until(
                    EC.any_of(
                        EC.url_contains("myaccount.google.com"),
                        EC.url_contains("google.com/search"),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-ved]"))
                    )
                )
                
                # Simulate post-login pause
                self.behavior_simulator.reading_pause(3, 7)
                
                logger.info("Successfully logged into Google account")
                return True
                
        except Exception as e:
            logger.error(f"Failed to login to Google account: {e}")
            return False
    
    def execute_activity_session(self, account: AccountInfo) -> Dict[str, Any]:
        """Execute a complete activity session for the account"""
        self.session_start_time = datetime.now()
        session_results = {
            'account_email': account.email,
            'session_start': self.session_start_time.isoformat(),
            'session_end': None,
            'total_duration': 0,
            'activities_performed': 0,
            'successful_activities': 0,
            'failed_activities': 0,
            'activity_results': [],
            'success': False,
            'error_message': None
        }
        
        try:
            with LoggingContext(logger, 
                              activity="account_activity_session", 
                              account_email=account.email):
                
                logger.info(f"Starting activity session for account: {account.email}")
                
                # Setup driver
                if not self._setup_driver():
                    raise Exception("Failed to setup Chrome driver")
                
                # Login to Google
                if not self.login_to_google(account):
                    raise Exception("Failed to login to Google account")
                
                # Execute YouTube activities
                if self.config.max_youtube_videos > 0:
                    logger.info("Starting YouTube activities")
                    youtube_results = self.youtube_manager.execute_youtube_activity(self.config)
                    self.activity_results.extend(youtube_results)
                    
                    # Random delay between activity types
                    if youtube_results:
                        delay = random.randint(*self.config.delay_between_activities)
                        logger.info(f"Waiting {delay} seconds before next activity type")
                        time.sleep(delay)
                
                # Execute Gmail activities
                if self.config.gmail_recipients:
                    logger.info("Starting Gmail activities")
                    self.gmail_manager.navigate_to_gmail()
                    
                    for recipient in self.config.gmail_recipients[:2]:  # Limit to 2 emails
                        result = self.gmail_manager.compose_and_send_email(recipient)
                        self.activity_results.append(result)
                        
                        if result.status == ActivityStatus.COMPLETED:
                            delay = random.randint(30, 90)
                            time.sleep(delay)
                
                # Execute Profile activities
                if self.config.profile_update_fields:
                    logger.info("Starting Profile activities")
                    if self.profile_manager.navigate_to_profile():
                        if 'about' in self.config.profile_update_fields:
                            result = self.profile_manager.update_about_section()
                            self.activity_results.append(result)
                
                # Calculate session results
                session_end = datetime.now()
                total_duration = (session_end - self.session_start_time).total_seconds()
                
                successful_activities = len([r for r in self.activity_results if r.status == ActivityStatus.COMPLETED])
                failed_activities = len([r for r in self.activity_results if r.status == ActivityStatus.FAILED])
                
                session_results.update({
                    'session_end': session_end.isoformat(),
                    'total_duration': total_duration,
                    'activities_performed': len(self.activity_results),
                    'successful_activities': successful_activities,
                    'failed_activities': failed_activities,
                    'activity_results': [self._result_to_dict(r) for r in self.activity_results],
                    'success': successful_activities > 0,
                    'success_rate': successful_activities / len(self.activity_results) if self.activity_results else 0
                })
                
                logger.info(f"Activity session completed. Duration: {total_duration:.1f}s, "
                          f"Successful: {successful_activities}, Failed: {failed_activities}")
                
        except Exception as e:
            session_results['error_message'] = str(e)
            logger.error(f"Activity session failed: {e}")
            
        finally:
            self._cleanup_driver()
            
            if not session_results['session_end']:
                session_results['session_end'] = datetime.now().isoformat()
                session_results['total_duration'] = (datetime.now() - self.session_start_time).total_seconds()
        
        return session_results
    
    def _result_to_dict(self, result: ActivityResult) -> Dict[str, Any]:
        """Convert ActivityResult to dictionary"""
        return {
            'activity_type': result.activity_type.value,
            'status': result.status.value,
            'start_time': result.start_time.isoformat(),
            'end_time': result.end_time.isoformat() if result.end_time else None,
            'duration': result.duration,
            'details': result.details,
            'error_message': result.error_message,
            'success_metrics': result.success_metrics
        }

# Convenience functions for easy usage
def execute_account_activities(account: AccountInfo, config: ActivityConfig = None) -> Dict[str, Any]:
    """Execute activities for a single account"""
    if config is None:
        config = ActivityConfig()
    
    manager = MainAccountActivityManager(config)
    return manager.execute_activity_session(account)

def create_default_activity_config(**kwargs) -> ActivityConfig:
    """Create default activity configuration with custom overrides"""
    return ActivityConfig(**kwargs) 