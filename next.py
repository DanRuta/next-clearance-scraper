import os
import time
import argparse
import smtplib, ssl
from email.message import EmailMessage

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


CONFIG = {}
CONFIG["scrape_url"] = "https://www.next.co.uk/clearance/search?w=*&af=gender:homeware"
CONFIG["to_emails"] = []
CONFIG["from_email"] = None
CONFIG["from_password"] = None
CONFIG["email_title"] = "Next scraping results"
CONFIG["chromedriver_exe_path"] = "C:/chromedriver.exe"
CONFIG["scrape_interval"] = 60 # Minutes

parser = argparse.ArgumentParser()
parser.add_argument("--u", default=None, help="Email sender address")
parser.add_argument("--p", default=None, help="Email sender password")
parser.add_argument("--t", default=None, type=int, help="Interval in minutes for scraping")
parser.add_argument("--to", default=None, help="Comma separated recipient email addresses")
args = parser.parse_args()

if CONFIG["from_email"] is None:
    CONFIG["from_email"] = args.u or input("Enter your sender email address and press enter: ")
if CONFIG["from_password"] is None:
    CONFIG["from_password"] = args.p or input("Enter your sender email password and press enter: ")
if not CONFIG["from_email"] or not CONFIG["from_password"]:
    raise "No complete credentials provided. Use --u and --p or hardcoded values"
if args.t is not None and args.t > 0:
    CONFIG["scrape_interval"] = args.t
if args.to is not None and len(args.to):
    CONFIG["to_emails"] = [i for i in args.to.split(",") if len(i)]
if len(CONFIG["to_emails"])==0:
    print("Warning: No recipient email addresses entered")


data_so_far = set()


def build_email_body (all_data):
    body = []
    for data in all_data:
        if len(data)>1 and len(data[0])>1:
            [name, price, orig_price, sizes, img_src] = data
            body.append(f'<div><div>{name}</div><img src="{img_src}"><div>{price}</div><div>{orig_price}</div></div><br><div>{sizes}</div><hr>')

    return "<br>".join(body)

def send_emails (data):

    body_data = build_email_body(data)
    to_emails = CONFIG["to_emails"]

    port = 465
    from_email = CONFIG["from_email"]
    password = CONFIG["from_password"]

    for to_email in to_emails:
        # Create a secure SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", port, context=context) as server:
            server.login(from_email, password)

            msg = EmailMessage()
            msg.set_content(body_data)
            msg.add_alternative(body_data, subtype='html')
            msg["Subject"] = CONFIG["email_title"]
            msg["From"] = from_email
            msg["To"] = to_email

            server.send_message(msg)
            server.quit()


def scrape_page (browser):

    browser.get(CONFIG["scrape_url"])
    browser.execute_script('let div=document.createElement("div");div.id="selenium_data";document.body.appendChild(div)')

    scraping_script = """
    Array.from(document.querySelectorAll(".search-result-item.multiple")).filter(el => {
        // Perform a check to see if the result item is of the desired type. Change this as needed
        const sizes = el.querySelector(".item-sizes-available")
        if (sizes) {
            // Rough pattern observed for sofa entries
            ["medium", "large", "xlge", "small", "snuggle", "airbed", "df small", "medbed"].forEach(size_type => {
                if (sizes.innerHTML.toLowerCase().includes(size_type)) {
                    return true
                }
            })
        }
        return false
    })
    .forEach(result => {
        const name = result.querySelector(".item-name").innerText
        const price = result.querySelector(".item-price.now").children[1].innerText
        const orig_price = result.querySelector(".item-price.original").innerHTML
        const sizes = result.querySelector(".item-sizes-available").innerHTML
        const img_src = result.querySelector("img.in").getAttribute('data-image-src')

        output = `${name}<,>${price}<,>${orig_price}<,>${sizes}<,>${img_src}<br>`
        selenium_data.innerHTML += output
    })
    """

    # Scroll the page down until all results are gathered
    old_height = None
    counter = 0
    while True:
        time.sleep(1)
        browser.execute_script("window.scrollBy(0,1000)")
        height = browser.execute_script("return document.body.scrollHeight")
        if old_height==height:
            # Give the page some time to load
            if counter>5:
                break
        else:
            old_height = height
            counter = 0
        counter += 1


    # Run the scraping
    browser.execute_script(scraping_script)

    data_out_elem = browser.find_element_by_css_selector("#selenium_data")
    data_out = data_out_elem.get_attribute('innerHTML')
    items = data_out.split("<br>")

    new_data = []
    for item in items:
        if item in data_so_far:
            pass
        else:
            data_so_far.add(item)
            data = item.split("&lt;,&gt;")
            new_data.append(data)

    if len(new_data):
        send_emails(new_data)

    with open("data_so_far.txt", "w+") as f:
        f.write("\n".join(data_so_far))






if __name__ == '__main__':

    # Read the so-far data
    if os.path.exists("data_so_far.txt"):
        with open("data_so_far.txt", "r") as f:
            lines = f.read().split("\n")
            for line in lines:
                data_so_far.add(line)


    chrome_options = Options()
    chrome_options.add_argument("--headless")
    browser = webdriver.Chrome(CONFIG["chromedriver_exe_path"], chrome_options=chrome_options)

    while True:
        scrape_page(browser)
        time.sleep(CONFIG["scrape_interval"]*1000)

    browser.quit()