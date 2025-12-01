# -*- coding: utf-8 -*-
import json
import time
import csv
from urllib.parse import urlparse
import traceback
import re

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def load_cookie_for_current_domain(driver, cookie_file):
    """根据当前 URL 域名自动过滤并加载匹配的 cookie"""
    try:
        current_host = urlparse(driver.current_url).hostname
        base_domain = "." + current_host.split(".", 1)[1]
        with open(cookie_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        driver.delete_all_cookies()
        for ck in cookies:
            ck.pop("sameSite", None)
            if "domain" in ck and ck["domain"].endswith(base_domain):
                try:
                    driver.add_cookie(ck)
                except:
                    pass
    except Exception as e:
        print(f"Cookie 加载失败: {e}")


def scroll_element_into_view(driver, element_xpath):
    """将指定的元素滚动到视野中心，触发懒加载"""
    try:
        element = driver.find_element(By.XPATH, element_xpath)
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
        time.sleep(1.5)
    except Exception:
        pass  # 找不到元素时忽略，由主逻辑处理


def exists(driver, xpath):
    """判断元素是否存在"""
    try:
        driver.find_element(By.XPATH, xpath)
        return True
    except:
        return False


def extract_text(driver, xpath):
    """安全获取文本"""
    try:
        return driver.find_element(By.XPATH, xpath).text.strip()
    except:
        return ""


def main():
    # ==== 配置区域 ====
    COOKIE_FILE = "cookie.json"
    # 替换目标商品链接
    PRODUCT_URL = "https://detail.tmall.com/item.htm?abbucket=8&id=787314648963&mi_id=0000Pu7LHcf1n435gyNxTSM-CIU9TZ_Sqp8q5UEsd4cLeU0&ns=1&priceTId=2147867b17635508483937806e111f&skuId=5505782805204&spm=a21n57.1.hoverItem.1&utparam=%7B%22aplus_abtest%22%3A%220f64c2fba8eb0e8872583866d78afd14%22%7D&xxc=taobaoSearch"   # 改成你要爬的商品链接
    CSV_FILE = "taobao_comments.csv"

    # ==== 启动浏览器 ====
    chrome_options = Options()
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    # 屏蔽一些日志输出
    chrome_options.add_argument("--log-level=3")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        # 1. 访问商品页面
        driver.get(PRODUCT_URL)
        time.sleep(2)

        # 2. 注入 Cookie
        load_cookie_for_current_domain(driver, COOKIE_FILE)
        driver.refresh()
        time.sleep(4)
        print("登录状态刷新完毕...")

        # 3. 点击 “评论” 按钮
        comment_btn_xpath = '//div[@class="tabDetailWrap--UUPrzQbC"]/div[1]/div[1]/div[4]/div[1]'
        WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, comment_btn_xpath))
        ).click()
        print("已打开评论弹窗")
        time.sleep(3)

        # ==== 准备工作 ====
        print("开始加载评论...")
        comments = []
        current_id = 1
        max_retries = 5
        retry_count = 0

        # 这里的 XPath 是列表的父容器，如果代码跑不通，请按 F12 检查是否是 div[7]
        base_list_xpath = '/html/body/div[7]/div[2]/div[2]/div[3]'

        print("\n" + "=" * 40)
        print("🚀 开始爬取评论")
        print("💡 提示：在终端按 Ctrl + C 可随时停止并保存数据")
        print("=" * 40 + "\n")

        # ==== 核心循环：增加异常捕获 ====
        try:
            while True:
                # 构造当前评论的 XPath
                current_item_xpath = f'{base_list_xpath}/div[{current_id}]'
                buyer_xpath = current_item_xpath + '/div[1]/div[2]/div[1]/span[1]'
                content_xpath = current_item_xpath + '/div[2]/div[1]'
                time_xpath = current_item_xpath + '/div[1]/div[2]/div[2]'

                # 检查当前数据是否存在
                if exists(driver, buyer_xpath):
                    buyer = extract_text(driver, buyer_xpath)
                    content = extract_text(driver, content_xpath)
                    raw_time = extract_text(driver, time_xpath)  # 先获取原始文本
                    # 匹配模式：4位数字 + 年 + 1到2位数字 + 月 + 1到2位数字 + 日
                    match = re.search(r'(\d{4}年\d{1,2}月\d{1,2}日)', raw_time)
                    if match:
                        comment_time = match.group(1)  # 提取匹配到的日期部分
                    else:
                        comment_time = raw_time  # 如果匹配失败（极少情况），保留原文本防止报错
                    # ==========================

                    comments.append([buyer, content, comment_time])
                    print(f"[{current_id}] 提取成功: {buyer[:5]}... - {comment_time}")

                    retry_count = 0
                    current_id += 1

                    # 策略：每爬 4 条，就去滚动一下刚刚爬到的这一条
                    # 这样可以保证当前视口一直往下走
                    if current_id % 20 == 0:
                        scroll_element_into_view(driver, current_item_xpath)

                else:
                    # 如果找不到，说明到底部了 或者 没加载出来
                    print(f"⏳ 第 {current_id} 条未加载，尝试滚动加载... ({retry_count + 1}/{max_retries})")

                    # 滚动到上一条已经存在的评论，强制触发浏览器懒加载
                    if current_id > 1:
                        last_real_xpath = f'{base_list_xpath}/div[{current_id - 1}]'
                        scroll_element_into_view(driver, last_real_xpath)
                    else:
                        print("❌ 这里的 XPath 可能变了，未找到第一条评论。")
                        break

                    retry_count += 1
                    if retry_count >= max_retries:
                        print("✅ 似乎已到达底部，自动停止。")
                        break

        except KeyboardInterrupt:
            # 这里专门捕获 Ctrl+C
            print("\n\n🛑 检测到手动停止 (KeyboardInterrupt)！")
            print("正在准备保存已抓取的数据...")

        # ==== 保存 CSV ====
        if comments:
            with open(CSV_FILE, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["买家", "评论", "评论时间"])
                writer.writerows(comments)
            print(f"\n💾 成功保存 {len(comments)} 条评论至：{CSV_FILE}")
        else:
            print("\n⚠️ 列表为空，未保存任何数据。")

    except Exception as e:
        print(f"发生未预期的错误: {e}")
        traceback.print_exc()

    finally:
        # 无论如何最后关闭浏览器
        driver.quit()
        print("浏览器已关闭。")


if __name__ == "__main__":
    main()