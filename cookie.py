from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json

driver = webdriver.Chrome()
driver.get("https://login.taobao.com/")

print("请扫码登录…")

# 等待跳转到非 login.taobao.com 的网址
WebDriverWait(driver, 300).until(
    lambda d: "login.taobao.com" not in d.current_url
)

print("检测到已成功登录，当前网址：", driver.current_url)

# 获取完整 cookie
cookies = driver.get_cookies()

with open("cookie.json", "w", encoding="utf-8") as f:
    json.dump(cookies, f, ensure_ascii=False, indent=2)

print("已成功导出 cookie 到 cookie.json")
driver.quit()
