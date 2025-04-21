import requests
from bs4 import BeautifulSoup
import os
import re
import argparse
from urllib.parse import urlparse
import time
import subprocess
import sys
import json
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
import getpass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("web_automation.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_user_input(prompt, options=None, default=None):
    """Get validated input from user with options and default value"""
    if options:
        options_str = '/'.join(options)
        prompt = f"{prompt} ({options_str})"
        if default:
            prompt = f"{prompt} [default: {default}]"
    
    prompt += ": "
    
    while True:
        user_input = input(prompt) or default
        
        if not user_input and not default:
            print("Input cannot be empty. Please try again.")
            continue
            
        if options and user_input.lower() not in [opt.lower() for opt in options]:
            print(f"Invalid option. Please choose from: {', '.join(options)}")
            continue
            
        return user_input

def setup_browser_driver(browser_name):
    """Setup and return appropriate WebDriver based on browser name"""
    try:
        if browser_name.lower() == "chrome":
            options = webdriver.ChromeOptions()
            options.add_argument("--start-maximized")
            return webdriver.Chrome(service=ChromeService(), options=options)
        
        elif browser_name.lower() == "firefox":
            options = webdriver.FirefoxOptions()
            return webdriver.Firefox(service=FirefoxService(), options=options)
        
        elif browser_name.lower() == "edge":
            options = webdriver.EdgeOptions()
            options.add_argument("--start-maximized")
            return webdriver.Edge(service=EdgeService(), options=options)
        
        else:
            logger.error(f"Unsupported browser: {browser_name}")
            return None
            
    except Exception as e:
        logger.error(f"Error setting up {browser_name} driver: {str(e)}")
        return None

def capture_user_interaction(url, browser_name):
    """Open browser and let user interact with the page, then capture input data"""
    logger.info(f"Opening {browser_name} for interaction capture at {url}")
    driver = setup_browser_driver(browser_name)
    
    if not driver:
        logger.error("Failed to initialize browser driver")
        return None
    
    try:
        driver.get(url)
        print("\n" + "="*80)
        print(f"Browser opened to {url}")
        print("Please interact with the login form:")
        print("1. Enter your credentials (use dummy data for security)")
        print("2. DO NOT submit the form yet")
        print("3. After filling in the form, return here and press Enter")
        print("="*80)
        
        input("\nPress Enter when you've completed the form (but haven't submitted)...")
        
        # Capture form elements and values
        capture_data = {
            'url': url,
            'form_elements': [],
            'inputs': {}
        }
        
        # Find all input elements on the page
        input_elements = driver.find_elements(By.TAG_NAME, "input")
        
        # First, identify username and password fields
        username_field = None
        password_field = None
        
        for element in input_elements:
            try:
                element_type = element.get_attribute("type")
                element_id = element.get_attribute("id")
                element_name = element.get_attribute("name")
                element_value = element.get_attribute("value")
                
                # Check if it's visible and enabled
                if not element.is_displayed() or not element.is_enabled():
                    continue
                
                if element_type == "password":
                    password_field = element
                elif element_type in ["text", "email"] and element_value:
                    # If we find a filled text/email field, it's likely the username field
                    username_field = element
            except Exception as e:
                logger.warning(f"Error examining element: {str(e)}")
                continue
        
        # Capture username field
        if username_field:
            try:
                # Use a more reliable XPath generation approach
                username_xpath = get_reliable_xpath(driver, username_field)
                
                username_data = {
                    'type': username_field.get_attribute("type"),
                    'id': username_field.get_attribute("id"),
                    'name': username_field.get_attribute("name"),
                    'xpath': username_xpath,
                    'value': username_field.get_attribute("value")
                }
                
                capture_data['form_elements'].append(username_data)
                capture_data['inputs']['username'] = {
                    'element': username_data,
                    'value': username_field.get_attribute("value")
                }
            except Exception as e:
                logger.warning(f"Error capturing username field: {str(e)}")
        
        # Capture password field
        if password_field:
            try:
                # Use a more reliable XPath generation approach
                password_xpath = get_reliable_xpath(driver, password_field)
                
                password_data = {
                    'type': password_field.get_attribute("type"),
                    'id': password_field.get_attribute("id"),
                    'name': password_field.get_attribute("name"),
                    'xpath': password_xpath,
                    'value': password_field.get_attribute("value")
                }
                
                capture_data['form_elements'].append(password_data)
                capture_data['inputs']['password'] = {
                    'element': password_data,
                    'value': password_field.get_attribute("value")
                }
            except Exception as e:
                logger.warning(f"Error capturing password field: {str(e)}")
        
        # Find submit button - try multiple approaches
        submit_button = None
        
        # First try: Look for submit input or button
        submit_elements = driver.find_elements(By.XPATH, "//input[@type='submit'] | //button[@type='submit']")
        
        if submit_elements:
            submit_button = submit_elements[0]
        else:
            # Second try: Look for buttons with submit/login/sign in text
            submit_elements = driver.find_elements(By.XPATH, 
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit') or "
                "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login') or "
                "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign in')]")
            
            if submit_elements:
                submit_button = submit_elements[0]
            else:
                # Third try: Look for inputs with value containing login/sign in
                submit_elements = driver.find_elements(By.XPATH, 
                    "//input[contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login') or "
                    "contains(translate(@value, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign in')]")
                
                if submit_elements:
                    submit_button = submit_elements[0]
        
        # Capture submit button
        if submit_button:
            try:
                submit_xpath = get_reliable_xpath(driver, submit_button)
                
                capture_data['submit_button'] = {
                    'id': submit_button.get_attribute("id"),
                    'name': submit_button.get_attribute("name"),
                    'xpath': submit_xpath,
                    'text': submit_button.text
                }
            except Exception as e:
                logger.warning(f"Error capturing submit button: {str(e)}")
        
        logger.info(f"Captured {len(capture_data['form_elements'])} form elements")
        return capture_data
        
    except Exception as e:
        logger.error(f"Error during user interaction capture: {str(e)}")
        traceback.print_exc()
        return None
    finally:
        try:
            driver.quit()
        except:
            pass

def get_reliable_xpath(driver, element):
    """Generate a reliable XPath for the element using multiple approaches"""
    try:
        # Try to get the most reliable attributes first
        element_id = element.get_attribute("id")
        element_name = element.get_attribute("name")
        
        # If there's an ID, use it (most reliable)
        if element_id and element_id.strip():
            return f"//*[@id='{element_id}']"
        
        # If there's a name, use it (second most reliable)
        if element_name and element_name.strip():
            return f"//*[@name='{element_name}']"
        
        # Fall back to JavaScript XPath generation
        return driver.execute_script("""
        function getXPath(element) {
            if (element.id !== '')
                return "//*[@id='" + element.id + "']";
                
            if (element.name !== '')
                return "//*[@name='" + element.name + "']";
                
            var path = '';
            for (; element && element.nodeType == 1; element = element.parentNode) {
                var index = 1;
                for (var sibling = element.previousSibling; sibling; sibling = sibling.previousSibling) {
                    if (sibling.nodeType == Node.DOCUMENT_TYPE_NODE)
                        continue;
                        
                    if (sibling.nodeName == element.nodeName)
                        index++;
                }
                
                var tagName = element.nodeName.toLowerCase();
                var pathIndex = (index > 1 ? "[" + index + "]" : "");
                path = "/" + tagName + pathIndex + path;
            }
            
            return path.toLowerCase();
        }
        return getXPath(arguments[0]);
        """, element)
    except:
        # Last resort - use tag name and attributes
        tag_name = element.tag_name
        
        # Try to use a meaningful attribute if available
        for attr in ["placeholder", "aria-label", "title", "class"]:
            attr_value = element.get_attribute(attr)
            if attr_value and attr_value.strip():
                return f"//{tag_name}[@{attr}='{attr_value}']"
        
        # Very generic XPath that will likely need refinement
        return f"//{tag_name}"

def generate_xpath_selenium(driver, element):
    """Generate XPath for an element using Selenium"""
    try:
        # Try to generate XPath using JavaScript
        js_xpath = driver.execute_script("""
        function getPathTo(element) {
            if (element.id !== '')
                return "//*[@id='" + element.id + "']";
            if (element.name !== '')
                return "//*[@name='" + element.name + "']";
                
            var path = '';
            while (element) {
                var position = 1;
                var sibling = element;
                while (sibling = sibling.previousElementSibling) {
                    if (sibling.nodeName === element.nodeName) {
                        position++;
                    }
                }
                path = '/' + element.nodeName.toLowerCase() + '[' + position + ']' + path;
                element = element.parentNode;
                if (element.nodeType !== 1) {
                    break;
                }
            }
            return path;
        }
        return getPathTo(arguments[0]);
        """, element)
        
        return js_xpath
    except:
        # Fallback to simple attribute-based XPath
        if element.get_attribute("id"):
            return f"//*[@id='{element.get_attribute('id')}']"
        elif element.get_attribute("name"):
            return f"//*[@name='{element.get_attribute('name')}']"
        else:
            return None

def scrape_login_page(url, browser_name=None):
    """Scrape a login page to identify input fields and buttons"""
    logger.info(f"Scraping login page: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        if browser_name:
            # Use Selenium for scraping if browser specified
            driver = setup_browser_driver(browser_name)
            if not driver:
                logger.error("Failed to setup browser for scraping")
                return None
                
            try:
                driver.get(url)
                # Wait for page to load
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                # Get page source
                html_content = driver.page_source
                
                # Process with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
            finally:
                driver.quit()
        else:
            # Use requests for scraping
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find form elements
        forms = soup.find_all('form')
        if not forms:
            logger.warning("No forms found on the page")
            # Try finding input elements directly
            inputs = soup.find_all('input')
            if not inputs:
                logger.error("No input elements found on the page")
                return None
            
            # Create a virtual form
            login_form = soup
        else:
            # Find the form that is most likely to be a login form
            login_form = None
            for form in forms:
                inputs = form.find_all('input', {'type': 'password'})
                if inputs:
                    login_form = form
                    break
            
            if not login_form:
                login_form = forms[0]  # Use the first form if no obvious login form
        
        # Find input fields
        input_fields = login_form.find_all('input')
        
        login_elements = {
            'username_field': None,
            'password_field': None,
            'submit_button': None,
            'form_action': getattr(login_form, 'get', lambda x, y: '')('action', '')
        }
        
        # Extract username and password fields
        for field in input_fields:
            field_type = field.get('type', '').lower()
            field_name = field.get('name', '').lower()
            field_id = field.get('id', '').lower()
            
            # Identify username field
            if field_type == 'text' or field_type == 'email' or 'user' in field_name or 'email' in field_name or 'login' in field_name:
                if not login_elements['username_field']:
                    login_elements['username_field'] = {
                        'name': field.get('name', ''),
                        'id': field.get('id', ''),
                        'xpath': generate_xpath(field)
                    }
            
            # Identify password field
            elif field_type == 'password':
                login_elements['password_field'] = {
                    'name': field.get('name', ''),
                    'id': field.get('id', ''),
                    'xpath': generate_xpath(field)
                }
            
            # Identify submit button
            elif field_type == 'submit' or field_type == 'button':
                login_elements['submit_button'] = {
                    'name': field.get('name', ''),
                    'id': field.get('id', ''),
                    'xpath': generate_xpath(field)
                }
        
        # If no submit button was found in inputs, look for button elements
        if not login_elements['submit_button']:
            buttons = login_form.find_all('button')
            for button in buttons:
                if button.get('type') == 'submit' or 'login' in button.text.lower() or 'sign in' in button.text.lower():
                    login_elements['submit_button'] = {
                        'name': button.get('name', ''),
                        'id': button.get('id', ''),
                        'xpath': generate_xpath(button)
                    }
        
        return login_elements
        
    except Exception as e:
        logger.error(f"Error scraping the login page: {str(e)}")
        traceback.print_exc()
        return None

def generate_xpath(element):
    """Generate an XPath for the given element"""
    if element.get('id'):
        return f"//*[@id='{element['id']}']"
    elif element.get('name'):
        return f"//*[@name='{element['name']}']"
    else:
        # Fallback to a more complex xpath if no id or name
        tag_name = element.name
        classes = element.get('class', [])
        class_str = " and ".join([f"contains(@class, '{cls}')" for cls in classes]) if classes else ""
        
        if class_str:
            return f"//{tag_name}[{class_str}]"
        else:
            return f"//{tag_name}"

def generate_ini_file(url, login_elements, browser_name, output_file):
    """Generate an INI file for ps_automate based on scraped login elements"""
    logger.info(f"Generating INI file: {output_file}")
    
    domain = urlparse(url).netloc
    
    try:
        with open(output_file, 'w') as f:
            # General section
            f.write("[General]\n")
            f.write(f"BrowserName={browser_name}\n")
            f.write(f"TargetURL={url}\n")
            f.write("EnableLogging=1\n")
            f.write("LogMethod=1\n")
            f.write("FixupPassword=1\n")
            f.write("GlobalSequenceDelay=250\n")
            f.write("KioskMode=0\n\n")
            
            # Credentials section (placeholder)
            f.write("[Credentials]\n")
            f.write("UserName=%username%\n")
            f.write("Password=%password%\n\n")
            
            # Task sequences
            sequence_num = 1
            
            # Task 1 & 2: Enter username (if present)
            if login_elements.get('username_field'):
                # Be sure to use the most reliable identifier
                if login_elements['username_field'].get('xpath'):
                    username_xpath = login_elements['username_field']['xpath']
                elif login_elements['username_field'].get('id'):
                    username_xpath = f"//*[@id='{login_elements['username_field']['id']}']"
                elif login_elements['username_field'].get('name'):
                    username_xpath = f"//*[@name='{login_elements['username_field']['name']}']"
                else:
                    username_xpath = "//input[@type='text' or @type='email'][1]"
                
                # Clear the field
                f.write(f"[TaskSequence{sequence_num}]\n")
                f.write(f"XPathElement={username_xpath}\n")
                f.write("XPathValue=%username%\n")
                f.write("XPathAction=clear\n")
                f.write("SequenceDelay=500\n\n")
                sequence_num += 1
                
                # Enter the username
                f.write(f"[TaskSequence{sequence_num}]\n")
                f.write(f"XPathElement={username_xpath}\n")
                f.write("XPathValue=%username%\n")
                f.write("SequenceDelay=500\n\n")
                sequence_num += 1
            else:
                logger.warning("No username field identified")
            
            # Task 3 & 4: Enter password (if present)
            if login_elements.get('password_field'):
                # Be sure to use the most reliable identifier
                if login_elements['password_field'].get('xpath'):
                    password_xpath = login_elements['password_field']['xpath']
                elif login_elements['password_field'].get('id'):
                    password_xpath = f"//*[@id='{login_elements['password_field']['id']}']"
                elif login_elements['password_field'].get('name'):
                    password_xpath = f"//*[@name='{login_elements['password_field']['name']}']"
                else:
                    password_xpath = "//input[@type='password'][1]"
                
                # Clear the field
                f.write(f"[TaskSequence{sequence_num}]\n")
                f.write(f"XPathElement={password_xpath}\n")
                f.write("XPathValue=%password%\n")
                f.write("XPathAction=clear\n")
                f.write("SequenceDelay=500\n\n")
                sequence_num += 1
                
                # Enter the password
                f.write(f"[TaskSequence{sequence_num}]\n")
                f.write(f"XPathElement={password_xpath}\n")
                f.write("XPathValue=%password%\n")
                f.write("SequenceDelay=500\n\n")
                sequence_num += 1
            else:
                logger.warning("No password field identified")
            
            # Task 5: Click submit button (if present)
            if login_elements.get('submit_button'):
                # Be sure to use the most reliable identifier
                if login_elements['submit_button'].get('xpath'):
                    submit_xpath = login_elements['submit_button']['xpath']
                elif login_elements['submit_button'].get('id'):
                    submit_xpath = f"//*[@id='{login_elements['submit_button']['id']}']"
                elif login_elements['submit_button'].get('name'):
                    submit_xpath = f"//*[@name='{login_elements['submit_button']['name']}']"
                else:
                    # Fallback to a typical submit button selector
                    submit_xpath = "//input[@type='submit'] | //button[@type='submit'] | //button[contains(text(), 'Sign in') or contains(text(), 'Login')]"
                
                f.write(f"[TaskSequence{sequence_num}]\n")
                f.write(f"XPathElement={submit_xpath}\n")
                f.write("XPathAction=click\n")
                f.write("SequenceDelay=1000\n")
            else:
                logger.warning("No submit button identified")
                
                # If no submit button is identified, add a fallback Submit action
                f.write(f"[TaskSequence{sequence_num}]\n")
                f.write("XPathAction=SendKeys\n")
                f.write("XPathValue={ENTER}\n")
                f.write("SequenceDelay=1000\n")
        
        logger.info(f"INI file generated: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error generating INI file: {str(e)}")
        return None

def generate_au3_script(url, login_elements, browser_name, output_file):
    """Generate an AutoIt script for automation based on scraped login elements"""
    logger.info(f"Generating AU3 script: {output_file}")
    
    domain = urlparse(url).netloc
    app_name = domain.split('.')[0].capitalize()
    
    # Map browser name to executable and window class
    browser_info = {
        "chrome": {
            "exe": "chrome.exe",
            "class": "Chrome_WidgetWin_1",
            "title": "Google Chrome"
        },
        "firefox": {
            "exe": "firefox.exe",
            "class": "MozillaWindowClass",
            "title": "Mozilla Firefox"
        },
        "edge": {
            "exe": "msedge.exe",
            "class": "Chrome_WidgetWin_1",
            "title": "Microsoft Edge"
        }
    }
    
    browser_details = browser_info.get(browser_name.lower())
    
    try:
        with open(output_file, 'w') as f:
            f.write("#cs ----------------------------------------------------------------------------\n")
            f.write(" AutoIt Version: 3.3.14.4\n")
            f.write(f" Author:       Web Scraper\n")
            f.write(f" Script Function:\n")
            f.write(f"\tAutoIt script for {app_name} login automation.\n")
            f.write("#ce ----------------------------------------------------------------------------\n")
            f.write("#include <Constants.au3>\n")
            f.write("#include <AutoItConstants.au3>\n")
            f.write("#include <MsgBoxConstants.au3>\n\n")
            
            # Add error handling function
            f.write("Func _ErrorHandler()\n")
            f.write("\tLocal $error = @error\n")
            f.write("\tIf $error Then\n")
            f.write('\t\tConsoleWrite("Error: " & $error & @CRLF)\n')
            f.write('\t\tMsgBox($MB_ICONERROR, "Error", "An error occurred: " & $error)\n')
            f.write("\t\tExit $error\n")
            f.write("\tEndIf\n")
            f.write("EndFunc\n\n")
            
            # Main script
            f.write("If $CmdLine[0] < 2 Then\n")
            f.write(f'   MsgBox($MB_OK, "Usage", "{domain}_login <username> <password>")\n')
            f.write("Else\n")
            f.write(f"   {domain}_login($CmdLine[1], $CmdLine[2])\n")
            f.write("EndIf\n\n")
            
            # Main login function
            f.write(f"Func {domain}_login($username, $password)\n")
            f.write("\tLocal $error = 0\n")
            f.write(f'\t; Run the browser with the target URL\n')
            f.write(f'\tRun("{browser_details["exe"]} {url}")\n')
            f.write('\tSleep(2000)\n')
            
            # Wait for page to load with timeout
            f.write(f'\t; Wait for the page to load\n')
            f.write(f'\tLocal $hWnd = WinWait("[CLASS:{browser_details["class"]}]", "", 30)\n')
            f.write('\tIf $hWnd = 0 Then\n')
            f.write(f'\t\tMsgBox($MB_ICONERROR, "Error", "Failed to find {browser_details["title"]} window")\n')
            f.write('\t\tReturn False\n')
            f.write('\tEndIf\n')
            f.write('\tWinActivate($hWnd)\n')
            f.write('\tSleep(2000)\n\n')
            
            # Add retry mechanism
            f.write('\t; Set retry counter\n')
            f.write('\tLocal $retryCount = 3\n')
            f.write('\tLocal $success = False\n\n')
            f.write('\tWhile $retryCount > 0 And Not $success\n')
            f.write('\t\tTry\n')
            
            # Enter username
            if login_elements.get('username_field') and login_elements['username_field'].get('id'):
                f.write(f'\t\t\t; Enter username\n')
                element_id = login_elements['username_field']['id']
                f.write(f'\t\t\tControlFocus($hWnd, "", "[ID:{element_id}]")\n')
                f.write(f'\t\t\tControlSend($hWnd, "", "[ID:{element_id}]", "")\n')  # Clear field
                f.write(f'\t\t\tControlSend($hWnd, "", "[ID:{element_id}]", $username)\n')
                f.write('\t\t\tSleep(800)\n\n')
            else:
                f.write(f'\t\t\t; Enter username (using Send)\n')
                f.write('\t\t\tSend($username, 1)\n')
                f.write('\t\t\tSleep(800)\n')
                f.write('\t\t\tSend("{TAB}")\n')
                f.write('\t\t\tSleep(500)\n\n')
            
            # Enter password
            if login_elements.get('password_field') and login_elements['password_field'].get('id'):
                f.write(f'\t\t\t; Enter password\n')
                element_id = login_elements['password_field']['id']
                f.write(f'\t\t\tControlFocus($hWnd, "", "[ID:{element_id}]")\n')
                f.write(f'\t\t\tControlSend($hWnd, "", "[ID:{element_id}]", "")\n')  # Clear field
                f.write(f'\t\t\tControlSend($hWnd, "", "[ID:{element_id}]", $password)\n')
                f.write('\t\t\tSleep(800)\n\n')
            else:
                f.write(f'\t\t\t; Enter password (using Send)\n')
                f.write('\t\t\tSend($password, 1)\n')
                f.write('\t\t\tSleep(800)\n\n')
            
            # Click submit button
            if login_elements.get('submit_button') and login_elements['submit_button'].get('id'):
                f.write(f'\t\t\t; Click submit button\n')
                element_id = login_elements['submit_button']['id']
                f.write(f'\t\t\tControlClick($hWnd, "", "[ID:{element_id}]")\n')
                f.write('\t\t\t$success = True\n')
            else:
                f.write(f'\t\t\t; Submit the form\n')
                f.write('\t\t\tSend("{ENTER}")\n')
                f.write('\t\t\t$success = True\n')
            
            # Error handling block
            f.write('\t\tCatch\n')
            f.write('\t\t\t$retryCount = $retryCount - 1\n')
            f.write('\t\t\tConsoleWrite("Login attempt failed. Retries left: " & $retryCount & @CRLF)\n')
            f.write('\t\t\tSleep(2000)\n')
            f.write('\t\tEndTry\n')
            f.write('\tWEnd\n\n')
            
            # Final status
            f.write('\tIf $success Then\n')
            f.write('\t\tConsoleWrite("Login process completed successfully" & @CRLF)\n')
            f.write('\t\tReturn True\n')
            f.write('\tElse\n')
            f.write('\t\tConsoleWrite("Failed to complete login process after multiple attempts" & @CRLF)\n')
            f.write('\t\tReturn False\n')
            f.write('\tEndIf\n')
            f.write('EndFunc ;==>login\n')
        
        logger.info(f"AU3 script generated: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error generating AU3 script: {str(e)}")
        return None

def test_ps_automate(ini_file, url, browser_name, username, password):
    """Test the generated INI file with ps_automate utility"""
    try:
        # Check if ps_automate exists
        ps_automate_path = "ps_automate.exe"
        if not os.path.exists(ps_automate_path):
            logger.error("ps_automate.exe not found. Cannot test INI file.")
            return False
            
        # Build command
        cmd = [
            ps_automate_path,
            f"ini={ini_file}",
            f"TargetURL={url}",
            f"BrowserName={browser_name}"
        ]
        
        if username:
            cmd.append(f"username={username}")
        if password:
            cmd.append(f"password={password}")
            
        # Execute command
        logger.info(f"Testing with ps_automate: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("ps_automate test successful")
            return True
        else:
            logger.error(f"ps_automate test failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error testing ps_automate: {str(e)}")
        return False

def main():
    try:
        print("\n===== Web Login Automation Script Generator =====\n")
        
        # Ask for operation mode
        mode = get_user_input(
            "Choose operation mode",
            options=["scrape", "capture"],
            default="scrape"
        )
        
        # Ask which script to generate
        script_type = get_user_input(
            "Which script type to generate",
            options=["ini", "au3", "both"],
            default="both"
        )
        
        # Ask for browser
        browser_name = get_user_input(
            "Which browser to use",
            options=["chrome", "firefox", "edge"],
            default="chrome"
        )
        
        # Ask for URL
        url = get_user_input("Enter the login page URL")
        
        login_elements = None
        
        if mode.lower() == "capture":
            # Use interactive capture mode
            print("\nStarting interactive capture mode...")
            captured_data = capture_user_interaction(url, browser_name)
            
            if captured_data:
                # Convert captured data to login_elements format
                login_elements = {
                    'username_field': None,
                    'password_field': None,
                    'submit_button': None
                }
                
                for element in captured_data['form_elements']:
                    if element['type'] == 'text' or element['type'] == 'email':
                        login_elements['username_field'] = {
                            'name': element['name'],
                            'id': element['id'],
                            'xpath': element['xpath']
                        }
                    elif element['type'] == 'password':
                        login_elements['password_field'] = {
                            'name': element['name'],
                            'id': element['id'],
                            'xpath': element['xpath']
                        }
                
                if 'submit_button' in captured_data:
                    login_elements['submit_button'] = captured_data['submit_button']
            else:
                logger.error("Failed to capture user interaction data")
                return
        else:
            # Use automatic scraping mode
            print("\nStarting automatic scraping mode...")
            login_elements = scrape_login_page(url, browser_name)
            
            if not login_elements:
                logger.error("Failed to extract login elements from the page")
                return
        
        # Generate requested scripts
        domain = urlparse(url).netloc.replace(".", "_")
        
        if script_type.lower() in ["ini", "both"]:
            ini_file = f"{domain}_login.ini"
            ini_path = generate_ini_file(url, login_elements, browser_name, ini_file)
            
            if ini_path:
                print(f"\n✅ INI file generated: {ini_path}")
                print(f"To use with ps_automate:")
                print(f"ps_automate.exe ini=\"{ini_path}\" TargetURL=\"{url}\" BrowserName=\"{browser_name}\" username=\"your_username\" password=\"your_password\"")
                
                # Ask if user wants to test the INI file
                test_ini = get_user_input("Do you want to test the INI file with ps_automate?", ["yes", "no"], "no")
                if test_ini.lower() == "yes":
                    username = input("Enter username for testing (or leave empty): ")
                    password = getpass.getpass("Enter password for testing (or leave empty): ")
                    test_ps_automate(ini_path, url, browser_name, username, password)
            else:
                print("\n❌ Failed to generate INI file")
        
        if script_type.lower() in ["au3", "both"]:
            au3_file = f"{domain}_login.au3"
            au3_path = generate_au3_script(url, login_elements, browser_name, au3_file)
            
            if au3_path:
                print(f"\n✅ AU3 script generated: {au3_path}")
                print(f"To use the AutoIt script:")
                print(f"{domain}_login.exe your_username your_password")
            else:
                print("\n❌ Failed to generate AU3 script")
        
        print("\nAutomation scripts generation completed!")
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    main()