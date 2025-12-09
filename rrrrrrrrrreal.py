# -*- coding: utf-8 -*-
"""
파이썬 Flask와 Selenium을 사용한 퍼스널 컬러 측정 및 상품 추천 웹 애플리케이션

이 프로그램은 사용자가 사진을 업로드하면 얼굴을 분석하여
퍼스널 컬러를 진단하고, 그 결과에 맞는 무신사 쇼핑몰 상품을 추천합니다.
"""

# 프로그램 실행 전, 아래 명령어를 터미널에 입력하여 필요한 라이브러리를 설치하세요.
# pip install Flask opencv-python numpy selenium webdriver-manager
from PIL import Image
import boto3
import io
import os
import uuid
import cv2
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, render_template_string, redirect, url_for, send_from_directory, session, jsonify, render_template, send_file
import threading

# Selenium 관련 라이브러리 추가
from selenium import webdriver as wb
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

# 위시리스트 전역캐시선언
server_wishlists = {}

# 이미지 데이터를 임시로 저장할 전역 캐시 딕셔너리 추가
image_cache = {}


# Flask 애플리케이션 인스턴스를 생성합니다.
app = Flask(__name__, static_folder='static')
app.secret_key = 'super_secret_key' # 세션 사용을 위한 비밀 키 설정

# static 폴더의 위치를 server 폴더 내로 지정합니다.
UPLOAD_FOLDER = os.path.join(app.root_path, 'static')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# 퍼스널 컬러별 특징과 컬러 팔레트 데이터를 정의합니다.
personal_color_data = {
    '봄웜': {
        'title': 'spring <span class="font-bold text-red-500">봄 웜</span>',
        'korean_name': '봄 웜',
        'hashtags': ['#화사한', '#생기있는', '#깨끗한', '#청순한', '#따뜻한'],
        'description': [
            ' - <b>봄 웜</b>은 노란빛 베이스의 맑고 화사한 컬러들로 이루어져 있어 <b>생기 넘치고 사랑스러운 분위기</b>를 줍니다.',
            ' - 피부톤이 <b>투명하고 붉은 기</b>가 있어도 <b>노란 기</b>를 가진 경우가 많으며, 대체적으로 밝고 맑은 인상을 줍니다.',
        ],
        'palette': ["#FA9D9D", "#FDB3FD", '#FEC16B', '#B1EE99'],
        'palette_description': '맑고 화사한 <b>옐로우</b>, <b>복숭아</b>, <b>연두색</b>, <b>코랄 핑크</b> 등 채도가 높고 따뜻한 색상이 잘 어울립니다.',
        'background': 'linear-gradient(to bottom, #FFF7D9, #FFD9D9)',
        'suitable_makeup': '<b>피치</b>, <b>살구</b>, <b>코랄</b> 계열의 립과 블러셔로 생기를 더하고, 따뜻한 <b>브라운</b> 아이섀도로 자연스러운 눈매를 연출하세요.',
        'main_fashion': '부드러운 <b>니트</b>, <b> 밝은 셔츠</b>등 화사한 느낌의 가볍고 사랑스러운 느낌의 의류가 잘 맞습니다.',
        'celebrities': [
            {'name': '배우 수지', 'image_url': 'celebrities/suzi.png'},
            {'name': '배우 이종석', 'image_url': 'celebrities/jong.jpg'},
            {'name': '가수 아이유', 'image_url': 'celebrities/IU.png'},
            {'name': '배우 박보검', 'image_url': 'celebrities/bo.jpg'},
        ],
        'emoji': '🌸'
    },
    '여름쿨': {
        'title': 'summer <span class="font-bold text-blue-500">여름 쿨</span>',
        'korean_name': '여름 쿨',
        'hashtags': ['#맑은', '#싱그러운', '#시원한', '#은은한', '#청량한'],
        'description': [
            ' - <b>여름 쿨</b>은 <b>블루 베이스</b>로 한 파스텔 계열이나 회색이 섞인 컬러로 이루어져 있고 <b>청량감 넘치고 시원하고 차분한 분위기</b>를 지녔어요.',
            ' - <b>여름 쿨</b>은 피부색이 <b>투명하고 붉은 기</b>를 가지고 있어서 인상은 <b>차분하면서도 청량감</b>이 넘쳐요.',
        ],
        'palette': ["#4584F8", '#B2D8E6', "#03F7E2", '#D2FCBA'],
        'palette_description': '시원하고 부드러운 <b>파스텔 톤</b>, <b>라벤더</b>, <b>민트</b>, <b>스카이 블루</b> 등이 잘 어울립니다.',
        'background': 'linear-gradient(to bottom, #B2D8E6, #4584F8)',
        'suitable_makeup': '<b>핑크</b>, <b>라벤더</b> 계열의 립과 섀도우를 사용해 청순하고 맑은 느낌을 강조하세요.',
        'main_fashion': '하늘하늘한 <b>블라우스</b>, 시원한 <b>린넨 소재</b>, <b>스트라이프 패턴</b> 등 깔끔하고 단아한 스타일이 좋습니다.',
        'celebrities': [
            {'name': '가수 윤아', 'image_url': 'celebrities/yuna.png'},
            {'name': '배우 박서준', 'image_url': 'celebrities/seonzun.png'},
            {'name': '가수 태연', 'image_url': 'celebrities/taeyeon.png'},
            {'name': '배우 정해인', 'image_url': 'celebrities/heain.png'},
        ],
        'emoji': '🐬'
    },
    '가을웜': {
        'title': 'fall <span class="font-bold text-orange-500">가을 웜</span>',
        'korean_name': '가을 웜',
        'hashtags': ['#따뜻한', '#부드러운', '#그윽한', '#편안한', '#차분한'],
        'description': [
            ' - <b>가을 웜</b>은 차분하고 무거운 분위기의 부드러운 컬러로 전반적으로 <b>고급스럽고 강렬하면서도 편안한 느낌</b>을 가지고 있어요.',
            ' - <b>가을 웜</b>은 부드러운 인상 속에 <b>우아한 분위기</b>를 풍겨서 어른스럽고 차분한 이미지를 가지고 있어요.',
        ],
        'palette': ['#8C5A4B', "#4E1703", "#235A20", "#5F2641"],
        'palette_description': '<b>카키</b>, <b>브라운</b>, <b>버건디</b>, <b>머스타드</b> 등 따뜻하고 깊이 있는 톤이 잘 어울립니다.',
        'background': 'linear-gradient(to bottom, #f0c179, #8C5A4B)',
        'suitable_makeup': '<b>말린 장미</b>, <b>벽돌색</b> 립과 <b>골드 브라운</b> 아이섀도로 그윽하고 우아한 분위기를 연출하세요.',
        'main_fashion': '차분하고 고급스러운 <b>트렌치코트</b>, <b>가죽 재킷</b>, <b>스웨이드 소재</b>와 같은 의류가 잘 맞습니다.',
        'celebrities': [
            {'name': '배우 김고은', 'image_url': 'celebrities/kimgoeun.png'},
            {'name': '배우 공유', 'image_url': 'celebrities/0you.png'},
            {'name': '가수 선미', 'image_url': 'celebrities/sunmi.png'},
            {'name': '배우 이동욱', 'image_url': 'celebrities/2dong.png'},
        ],
        'emoji': '🍂'
    },
    '겨울쿨': {
        'title': 'winter <span class="font-bold text-sky-500">겨울 쿨</span>',
        'korean_name': '겨울 쿨',
        'hashtags': ['#강렬한', '#선명한', '#차가운', '#카리스마', '#세련된'],
        'description': [
            ' - <b>겨울 쿨</b>은 <b>파랑 베이스</b>의 차갑고 선명한 원색이 잘 어울려 <b>모던하고 카리스마 있는 이미지</b>를 줍니다.',
            ' - <b>겨울 쿨</b>은 피부가 <b>창백하고 희거나 차분하고 어두운 톤</b>을 가지고 있으며, 흑백처럼 명도가 뚜렷한 색상이 잘 어울립니다.',
        ],
        'palette': ["#3A3669", "#7C3939", "#31552D", "#000000"],
        'palette_description': '<b>블랙</b>, <b>화이트</b>, 쨍한 <b>블루</b>, <b>마젠타</b> 등 선명하고 채도 높은 색상이 잘 어울립니다.',
        'background': 'linear-gradient(to bottom, #2F4F4F, #483D8B)',
        'suitable_makeup': '<b>레드</b>, <b>버건디</b>, <b>푸시아 핑크</b> 등 강렬한 컬러의 립을 사용하고, <b>선명한 아이라인</b>으로 포인트를 주세요.',
        'main_fashion': '차분하고 고급스러운 <b>트렌치코트</b>, <b>가죽 재킷</b>, <b>스웨이드 소재</b>와 같은 의류가 잘 맞습니다.',
        'celebrities': [
            {'name': '가수 현아', 'image_url': 'celebrities/heona.png'},
            {'name': '가수 뷔', 'image_url': 'celebrities/bts.png'},
            {'name': '배우 정은채', 'image_url': 'celebrities/jung.png'},
            {'name': '가수 차은우', 'image_url': 'celebrities/cha.png'},
        ],
        'emoji': '❄️'
    }
}

# --- Selenium 웹 크롤링 함수 ---
def crawl_with_selenium(personal_color, gender, item_code):
    data_list = []
    
    # 무신사 컬러 코드 매핑
    color_map = {
        '봄웜': "RED%2CLIGHTORANGE%2CLIGHTPINK%2CPEACH",
        '여름쿨': "SKYBLUE%2CLIGHTGREEN%2CLIGHTBLUEDENIM%2CMINT",
        '가을웜': "BROWN%2CDARKBROWN%2CKHAKI%2CBURGUNDY",
        '겨울쿨': "DARKNAVY%2CDARKBULUE%2CDARKGREEN%2CPURPLE",
    }
    
    color_code = color_map.get(personal_color, "")
    gender_code = "F" if gender == 'female' else "M"
    
    url_img = f"https://www.musinsa.com/category/{item_code}?gf={gender_code}&color={color_code}"
    
    try:
        options = wb.ChromeOptions()
        options.add_argument('headless') # 웹 브라우저를 띄우지 않는 headless 모드
        options.add_argument("window-size=1920,1080")
        options.add_argument("disable-gpu")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.190 Safari/537.36")
        
        driver = wb.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url_img)
        time.sleep(3) # 페이지 로딩 대기
        
        # Selenium으로 요소 선택
        img_url_list = driver.find_elements(By.CSS_SELECTOR, 'img[src*="goods_img"][alt]')
        brand_list = driver.find_elements(By.CSS_SELECTOR, "span.text-etc_11px_semibold.font-pretendard")
        name_list = driver.find_elements(By.CSS_SELECTOR, "span.text-body_13px_reg.font-pretendard")
        price_list = driver.find_elements(By.XPATH, "//span[contains(@class, 'text-body_13px_semi') and contains(text(), '원')]")
        url_list = driver.find_elements(By.CSS_SELECTOR, 'a[aria-label="상품 상세로 이동"]')

        for i in range(min(40, len(img_url_list))):
            try:
                if (item_code == "103"):
                    img_url = img_url_list[i].get_attribute("src")
                    url = url_list[i].get_attribute('href')
                    brand = brand_list[i].text
                    name = name_list[i + 52].text # 인덱스 조정 필요
                    price = price_list[i].text
                
                    data_list.append({
                        'img_url': img_url,
                        'brand': brand,
                        'name': name,
                        'price': price,
                        'url': url
                    })
                else :
                    img_url = img_url_list[i].get_attribute("src")
                    url = url_list[i].get_attribute('href')
                    brand = brand_list[i].text
                    name = name_list[i + 7].text # 인덱스 조정 필요
                    price = price_list[i].text
                    
                    data_list.append({
                        'img_url': img_url,
                        'brand': brand,
                        'name': name,
                        'price': price,
                        'url': url
                    })
            except IndexError as e:
                print(f"Index error during data collection at index {i}: {e}")
                continue
    
    except Exception as e:
        print(f"Selenium crawling failed: {e}")
        # 오류 발생 시 빈 리스트 반환
        return []
    finally:
        if 'driver' in locals():
            driver.quit()

    return data_list

# --- HTML 템플릿 정의 (모바일 최적화) ---
HTML_START_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>퍼스널 컬러 진단</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body { font-family: 'Noto Sans KR', sans-serif; }
        .animate-bg {
            animation: background-gradient 12s ease infinite;
            background: linear-gradient(
                -45deg,
                #f3e7e9,
                #e3f9fd,
                #fff2f2,
                #e6e9f0,
                #ffe0ac,
                #ffd6e0,
                #c1f0f6,
                #d4c1ec
                );
            background-size: 400% 400%;
            }

        @keyframes background-gradient {
            0% { background-position: 0% 50%; }
            25% { background-position: 50% 100%; }
            50% { background-position: 100% 50%; }
            75% { background-position: 50% 0%; }
            100% { background-position: 0% 50%; }
        }
        .rotate-slow {
            animation: spin 15s linear infinite;
        }

        /* 모바일 최적화 */
        .mobile-card {
            padding: 1.5rem !important;
            border-radius: 1.5rem;
        }
        .mobile-h1 {
            font-size: 2.5rem; /* 4xl */
        }
        .mobile-text {
            font-size: 1.125rem; /* lg */
        }
    </style>
</head>
<body class="animate-bg flex flex-col items-center justify-center min-h-screen p-4 sm:p-6">

    <div class="bg-white/70 shadow-2xl rounded-3xl p-8 max-w-xl w-full text-center backdrop-blur-md mobile-card">
        <h2 class="text-xl font-normal text-gray-700 mb-2 mobile-text">나는 웜톤일까? 쿨톤일까?</h2>
        <h1 class="text-4xl font-bold text-gray-900 mb-8 mobile-h1">퍼스널 컬러 진단</h1>
        
        <div class="relative w-48 h-48 mx-auto mb-8">
            <div class="absolute inset-0 rounded-full rotate-slow" 
                style="background: conic-gradient(from 0deg, #FF69B4, #8A2BE2, #00BFFF, #32CD32, #FFD700, #FF6347, #FF69B4);">
            </div>
            <div class="absolute inset-4 bg-white rounded-full flex items-center justify-center shadow-inner">
                <span class="text-6xl font-bold text-gray-800">?</span>
            </div>
        </div>

        <p class="text-lg font-medium text-gray-700 mb-3 mobile-text">얼굴 사진을 업로드하면 간단한 분석을 통해</p>
        <p class="text-lg font-medium text-gray-700 mb-8 mobile-text">당신의 퍼스널 컬러를 진단해 드립니다.</p>
        
        <p class="text-sm text-gray-600 font-medium mb-8">
            ⚠️ 이 프로그램은 데모용으로, 결과는 참고용으로만 사용해주세요!
        </p>

        <a href="/select_gender" 
            class="w-full inline-block text-center bg-gradient-to-r from-pink-500 to-purple-500 text-white text-lg font-bold py-4 px-6 rounded-full
                hover:shadow-xl hover:scale-105 transition-transform duration-300">
            시작하기
        </a>
    </div>
</body>
</html>
"""

HTML_SELECT_GENDER_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>성별 선택</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body { 
            font-family: 'Noto Sans KR', sans-serif;
            background-color: #f7f7f7;
        }
        .gender-card {
            background-color: #fff;
            padding: 2rem;
            border-radius: 1rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            cursor: pointer;
            width: 150px;
            height: 200px;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            border: 2px solid transparent;
        }
        .gender-card.male.active {
            border-color: #60A5FA;
            box-shadow: 0 4px 20px rgba(96,165,250,0.3);
            transform: scale(1.05);
        }
        .gender-card.female.active {
        border-color: #EC4899;
        box-shadow: 0 4px 20px rgba(236,72,153,0.3);
        transform: scale(1.05);
        }
        .gender-symbol {
            font-size: 60px;
            margin-bottom: 1rem;
            transition: color 0.3s ease;
        }
        .gender-text {
            font-size: 1.2rem;
            font-weight: bold;
            transition: color 0.3s ease;
        }
        .gender-card.male .gender-symbol { color: #d1d5db; }
        .gender-card.male.active .gender-symbol { color: #60A5FA; }
        .gender-card.male .gender-text { color: #4B5563; }
        .gender-card.male.active .gender-text { color: #3B82F6; }

        .gender-card.female .gender-symbol { color: #d1d5db; }
        .gender-card.female.active .gender-symbol { color: #EC4899; }
        .gender-card.female .gender-text { color: #4B5563; }
        .gender-card.female.active .gender-text { color: #F472B6; }

        #next-button {
            pointer-events: none;
        }

        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1rem !important;
            }
            .mobile-h1 {
                font-size: 2.25rem !important; /* 4xl */
            }
            .mobile-text {
                font-size: 1rem !important; /* base */
            }
            
            .gender-card {
                width: 100%;
                max-width: 200px;
                height: auto;
                padding: 1.5rem;
            }
        }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4 sm:p-6 animate-bg">

    <div class="bg-white/70 shadow-2xl rounded-3xl p-8 max-w-xl w-full text-center backdrop-blur-md mobile-card">
        <h1 class="text-4xl font-bold text-gray-900 mb-4 mobile-h1">성별을 선택해주세요</h1>
        <p class="text-lg font-medium text-gray-700 mb-8 mobile-text">맞춤형 진단을 위해 필요해요</p>
        
        <div class="flex gap-12 justify-center mb-8 gender-container">
            <div class="gender-card male w-64 h-55" id="male-card">
                <span class="gender-symbol text-6xl">♂</span>
                <span class="gender-text text-xl font-bold">남자</span>
            </div>
            <div class="gender-card female w-64 h-55" id="female-card">
                <span class="gender-symbol text-6xl">♀</span>
                <span class="gender-text text-xl font-bold">여자</span>
            </div>
        </div>

        <a href="#" id="next-button"
            class="w-full inline-block text-center bg-gray-400 text-white text-lg font-bold py-4 px-6 rounded-full
                transition-colors duration-300 cursor-not-allowed">
            다음
        </a>
    </div>

    <script>
        const maleCard = document.getElementById('male-card');
        const femaleCard = document.getElementById('female-card');
        const nextButton = document.getElementById('next-button');

        let selectedGender = null;

        function updateSelection(card, gender) {
            if (selectedGender === gender) {
                card.classList.remove('active');
                selectedGender = null;
            } else {
                if (selectedGender) {
                    document.getElementById(selectedGender + '-card').classList.remove('active');
                }
                card.classList.add('active');
                selectedGender = gender;
            }
            
            if (selectedGender) {
                nextButton.classList.add('bg-indigo-600', 'hover:bg-indigo-700', 'hover:scale-105');
                nextButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
                nextButton.href = "/upload_page?gender=" + selectedGender;
                nextButton.style.pointerEvents = 'auto';
            } else {
                nextButton.classList.add('bg-gray-400', 'cursor-not-allowed');
                nextButton.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'hover:scale-105');
                nextButton.href = "#";
                nextButton.style.pointerEvents = 'none';
            }
        }

        maleCard.addEventListener('click', () => updateSelection(maleCard, 'male'));
        femaleCard.addEventListener('click', () => updateSelection(femaleCard, 'female'));

        // 초기 상태 설정
        nextButton.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'hover:scale-105');
        nextButton.classList.add('bg-gray-400', 'cursor-not-allowed');
        nextButton.style.pointerEvents = 'none';

    </script>
</body>
</html>
"""

HTML_UPLOAD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>사진 업로드</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body { font-family: 'Noto Sans KR', sans-serif; background-color: #f0f4f8; }
        .upload-box {
            position: relative;
            border-style: dashed;
            border-width: 2px;
            border-color: #d1d5db;
            background-color: #f9fafb;
            transition: all 0.3s ease;
            border-radius: 50%;
            width: 20rem;
            height: 20rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            margin: 0 auto;
        }
        .upload-box:hover {
            border-color: #9ca3af;
            background-color: #e5e7eb;
        }
        .image-preview {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }

        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1.5rem !important;
            }
            .mobile-h1 {
                font-size: 2.25rem !important; /* 4xl */
            }
            .mobile-text {
                font-size: 1rem !important; /* base */
            }
            .upload-box {
                width: 15rem;
                height: 15rem;
            }
            .upload-box .mobile-svg {
                width: 4rem;
                height: 4rem;
            }
            .upload-box p {
                font-size: 0.875rem;
            }
            .upload-box p.text-sm {
                font-size: 0.75rem;
            }
        }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4 sm:p-6 animate-bg">
    <div class="bg-white/70 shadow-2xl rounded-3xl p-8 max-w-xl w-full text-center backdrop-blur-md mobile-card">
        <h1 class="text-4xl font-bold text-gray-900 mb-4 mobile-h1">진단 방법을 선택해주세요</h1>
        <p class="text-lg font-medium text-gray-700 mb-8 mobile-text">사진을 업로드하거나, 카메라로 직접 촬영할 수 있습니다.</p>

        <div class="flex justify-center space-x-4 mb-6">
            <button id="upload-option" class="bg-indigo-600 text-white font-bold py-3 px-6 rounded-full transition-colors duration-300 transform hover:scale-105 text-base">
                사진 업로드
            </button>
            <button id="camera-option" class="bg-gray-400 text-white font-bold py-3 px-6 rounded-full transition-colors duration-300 transform hover:scale-105 text-base">
                카메라 촬영
            </button>
        </div>
        
        <form id="upload-form" method="post" action="/upload" enctype="multipart/form-data" class="space-y-6">
            
            <div id="upload-section">
                <div class="upload-box" id="image-container">
                    <img id="image-preview" src="" alt="업로드된 사진" class="image-preview hidden">
                    <div id="placeholder-content" class="flex flex-col items-center justify-center p-6">
                        <svg class="w-12 h-12 text-gray-400 mb-2 mobile-svg" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                            <path fill-rule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clip-rule="evenodd"></path>
                        </svg>
                        <p class="text-gray-500 font-medium text-sm">
                            여기에 이미지를 드래그하거나 <span class="font-bold text-indigo-500">클릭</span>하세요.
                        </p>
                        <p class="text-xs text-gray-400 mt-1">
                            (JPG, PNG, GIF 등 16MB 미만)
                        </p>
                    </div>
                </div>
                <input type="file" id="file-upload" name="file" accept="image/*" class="hidden">
            </div>

            <div id="camera-section" class="hidden space-y-6">
                <video id="video" width="100%" height="auto" class="rounded-2xl shadow-xl mx-auto"></video>
                <canvas id="canvas" class="hidden"></canvas>
                <button type="button" id="capture-button" class="w-full bg-indigo-600 text-white font-bold py-4 px-6 rounded-full hover:bg-indigo-700 transition-colors duration-300 transform hover:scale-105 text-base">
                    촬영하기
                </button>
            </div>
            
            <input type="hidden" name="gender" value="{{ gender }}">

            <div class="bg-gray-100 p-4 rounded-2xl text-gray-600 text-sm mt-4 space-y-2">
                <p>😊 안심하세요!</p>
                <p>본 서비스는 사용자의 사진을 수집하지 않으며,</p>
                <p>사진은 진단 외 다른 목적으로 이용되지 않습니다.</p>
            </div>

            <button type="submit" id="diagnose-button" disabled
                    class="w-full mt-6 bg-gray-400 text-white font-bold py-4 px-6 rounded-full
                            text-base transition-colors duration-300 cursor-not-allowed">
                진단시작
            </button>
        </form>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs"></script>
    <script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/blazeface"></script>
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            const fileInput = document.getElementById('file-upload');
            const imagePreview = document.getElementById('image-preview');
            const placeholderContent = document.getElementById('placeholder-content');
            const diagnoseButton = document.getElementById('diagnose-button');
            const imageContainer = document.getElementById('image-container');

            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const captureButton = document.getElementById('capture-button');
            const uploadOptionButton = document.getElementById('upload-option');
            const cameraOptionButton = document.getElementById('camera-option');
            const uploadSection = document.getElementById('upload-section');
            const cameraSection = document.getElementById('camera-section');

            let stream = null;

            // 사진 업로드 옵션 선택
            uploadOptionButton.addEventListener('click', () => {
                if (stream) {
                    stream.getTracks().forEach(track => track.stop());
                    video.srcObject = null;
                }
                uploadSection.classList.remove('hidden');
                cameraSection.classList.add('hidden');
                uploadOptionButton.classList.remove('bg-gray-400');
                uploadOptionButton.classList.add('bg-indigo-600');
                cameraOptionButton.classList.remove('bg-indigo-600');
                cameraOptionButton.classList.add('bg-gray-400');

                // 업로드 모드에서 진단 버튼 상태 초기화
                diagnoseButton.disabled = true;
                diagnoseButton.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'transform', 'hover:scale-105', 'cursor-pointer');
                diagnoseButton.classList.add('bg-gray-400', 'cursor-not-allowed');
            });

            // 카메라 촬영 옵션 선택
            cameraOptionButton.addEventListener('click', async () => {
                uploadSection.classList.add('hidden');
                cameraSection.classList.remove('hidden');
                uploadOptionButton.classList.remove('bg-indigo-600');
                uploadOptionButton.classList.add('bg-gray-400');
                cameraOptionButton.classList.remove('bg-gray-400');
                cameraOptionButton.classList.add('bg-indigo-600');

                try {
                    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                    video.srcObject = stream;
                    await video.play();
                    diagnoseButton.disabled = true; // 카메라 모드에서는 촬영 전까지 버튼 비활성화
                    diagnoseButton.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'transform', 'hover:scale-105', 'cursor-pointer');
                    diagnoseButton.classList.add('bg-gray-400', 'cursor-not-allowed');
                } catch (err) {
                    console.error("웹캠 접근 오류: " + err);
                    alert("카메라에 접근할 수 없습니다. 사진 업로드 기능을 이용해주세요.");
                    uploadOptionButton.click(); // 에러 발생 시 업로드 모드로 전환
                }
            });

            // 파일 선택 시 이미지 미리보기
            imageContainer.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', function(event) {
                const file = event.target.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        imagePreview.src = e.target.result;
                        imagePreview.classList.remove('hidden');
                        placeholderContent.classList.add('hidden');
                        diagnoseButton.disabled = false;
                        diagnoseButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
                        diagnoseButton.classList.add('bg-indigo-600', 'hover:bg-indigo-700', 'transform', 'hover:scale-105');
                    };
                    reader.readAsDataURL(file);
                }
            });
            
                        
            // 드래그 앤 드롭으로 파일 업로드
            imageContainer.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#4f46e5';
                e.currentTarget.style.backgroundColor = '#eef2ff';
            });
            imageContainer.addEventListener('dragleave', (e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#d1d5db';
                e.currentTarget.style.backgroundColor = '#f9fafb';
            });
            imageContainer.addEventListener('drop', (e) => {
                e.preventDefault();
                e.currentTarget.style.borderColor = '#d1d5db';
                e.currentTarget.style.backgroundColor = '#f9fafb';
                const file = e.dataTransfer.files[0];
                if (file && file.type.startsWith('image/')) {
                    fileInput.files = e.dataTransfer.files;
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        updateImagePreview(e.target.result);
                    };
                    // 이 부분이 중요합니다. fileInput에 파일이 할당된 후 change 이벤트를 수동으로 발생시킵니다.
                    fileInput.dispatchEvent(new Event('change'));
                    reader.readAsDataURL(file);
                }
            });


            // 촬영하기 버튼 클릭
            captureButton.addEventListener('click', () => {
                const context = canvas.getContext('2d');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                context.drawImage(video, 0, 0, canvas.width, canvas.height);

                // 캡처된 이미지를 Blob으로 변환
                canvas.toBlob((blob) => {
                    if (!blob) {
                        console.error('Blob 생성 실패');
                        alert('사진 캡처 중 오류가 발생했습니다.');
                        return;
                    }
                    
                    // Blob을 File 객체로 변환하여 input에 할당
                    const file = new File([blob], 'webcam-capture.jpeg', { type: 'image/jpeg' });
                    const dataTransfer = new DataTransfer();
                    dataTransfer.items.add(file);
                    fileInput.files = dataTransfer.files;

                    // 미리보기 업데이트 및 버튼 활성화
                    imagePreview.src = URL.createObjectURL(file);
                    imagePreview.classList.remove('hidden');
                    placeholderContent.classList.add('hidden');
                    diagnoseButton.disabled = false;
                    diagnoseButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
                    diagnoseButton.classList.add('bg-indigo-600', 'hover:bg-indigo-700', 'transform', 'hover:scale-105');

                    // 카메라 스트림 종료
                    if (stream) {
                        stream.getTracks().forEach(track => track.stop());
                        video.srcObject = null;
                    }

                    // 업로드 섹션을 다시 보이게
                    uploadSection.classList.remove('hidden');
                    cameraSection.classList.add('hidden');
                }, 'image/jpeg');
            });

            // 초기 상태는 사진 업로드 옵션으로 설정
            uploadOptionButton.click();
        });
    </script>
</body>
</html>
"""

HTML_RESULT_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>분석 결과</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body {
            font-family: 'Noto Sans KR', sans-serif;
            background: {{ data['background'] }};
            color: #374151; /* Tailwind's gray-700 */
        }
        .hashtag {
            background-color: #FFFFFF;
            color: #4B5563;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 600;
            border: 3px solid {{ data['palette'][0] }};
        }
        .celebrity-card {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
            margin-bottom: 1rem;
        }
        .celebrity-image {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            object-fit: cover;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
        }
        .section-title {
            color: black;
        }
        .divider {
            border-color: {{ data['palette'][0] }};
        }

        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1.5rem !important;
                border-radius: 1.5rem;
            }
            .mobile-h1 {
                font-size: 1.875rem !important; /* 3xl */
            }
            .mobile-text {
                font-size: 1rem !important; /* base */
            }
            .celebrity-image {
                width: 80px;
                height: 80px;
            }
            .grid-cols-2-mobile {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4 sm:p-6 animate-bg">

    <div class="bg-white/70 shadow-2xl rounded-3xl p-8 max-w-xl w-full text-center backdrop-blur-md mobile-card">
        <h1 class="text-4xl font-bold mb-4 text-gray-900 mobile-h1">
            당신은 <span style="color: {{ data['palette'][0] }};">{{ data['korean_name'] }}</span>입니다.
        </h1>
        
        <div class="flex flex-wrap justify-center gap-2 mb-8">
            {% for hashtag in data['hashtags'] %}
                <span class="hashtag text-sm py-1 px-3">{{ hashtag }}</span>
            {% endfor %}
        </div>

        <div class="mb-8">
            <div class="relative w-48 h-48 rounded-full overflow-hidden mx-auto" style="border: 5px solid {{ data['palette'][0] }};">
                <img src="{{ cropped_image_url }}" alt="크롭된 사진" class="w-full h-full object-cover">
            </div>
        </div>

        <div class="text-left text-gray-700 space-y-4">
            <h2 class="text-xl font-bold section-title">
                {{ data['emoji'] }} {{ data['korean_name'] }}의 <span style="color: {{ data['palette'][0] }};">특징</span>
            </h2>
            {% for desc in data['description'] %}
                <p class="text-sm leading-relaxed">{{ desc | safe }}</p>
            {% endfor %}

            <hr class="my-4 border-t-2 divider" style="border-style: dotted;" />
            
            <h2 class="text-xl font-bold mt-6 section-title">
                {{ data['emoji'] }} {{ data['korean_name'] }} <span style="color: {{ data['palette'][0] }};">컬러 팔레트</span>
            </h2>
            <p class="text-sm leading-relaxed">{{ data['palette_description'] | safe }}</p>
            <div class="flex flex-wrap justify-center gap-2 mt-2">
                {% for color in data['palette'] %}
                    <div class="w-12 h-12 rounded-full border-2 border-gray-300" style="background-color: {{ color }};"></div>
                {% endfor %}
            </div>

            <hr class="my-4 border-t-2 divider" style="border-style: dotted;" />
            
            <h2 class="text-xl font-bold mt-6 section-title">
                {{ data['emoji'] }} 어울리는 <span style="color: {{ data['palette'][0] }};">메이크업</span>
            </h2>
            <p class="text-sm leading-relaxed">{{ data['suitable_makeup'] | safe }}</p>
            
            <hr class="my-4 border-t-2 divider" style="border-style: dotted;" />

            <h2 class="text-xl font-bold mt-6 section-title">
                {{ data['emoji'] }} 어울리는 <span style="color: {{ data['palette'][0] }};">패션</span>
            </h2>
            <p class="text-sm leading-relaxed">{{ data['main_fashion'] | safe }}</p>
            
            <hr class="my-4 border-t-2 divider" style="border-style: dotted;" />

            {% if data['celebrities'] %}
            <h2 class="text-xl font-bold mt-6 section-title">
                {{ data['emoji'] }} {{ data['korean_name'] }} <span style="color: {{ data['palette'][0] }};">연예인</span>
            </h2>
            <div class="grid grid-cols-2-mobile sm:grid-cols-4 gap-4 mt-4">
                {% for celebrity in data['celebrities'] %}
                <div class="celebrity-card">
                    <img src="{{ url_for('static', filename=celebrity['image_url']) }}" alt="{{ celebrity['name'] }}" class="celebrity-image" style="border: 3px solid {{ data['palette'][0] }};">
                    <p class="mt-2 text-xs font-medium"><b>{{ celebrity['name'].split(' ')[0] }}</b> {{ celebrity['name'].split(' ')[1] }}</p>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>

        <a href="{{ url_for('select_item') }}"
            class="w-full inline-block text-white font-bold py-4 px-6 rounded-full
                    hover:shadow-xl hover:scale-105 transition-transform duration-300 mt-8 text-base"
            style="background-color: {{ data['palette'][0] }};">
            추천상품 보러가기
        </a>
    </div>
</body>
</html>
"""

HTML_SELECT_ITEM_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>아이템 선택</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body { 
            font-family: 'Noto Sans KR', sans-serif;
            background-color: #f7f7f7;
        }
        .item-card {
            background-color: #fff;
            padding: 2rem;
            border-radius: 1.5rem;
            box-shadow: 0 6px 16px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            cursor: pointer;
            border: 3px solid transparent;
            text-align: center;
        }
        .item-card.active {
            border-color: #3B82F6;
            box-shadow: 0 6px 24px rgba(59,130,246,0.3);
            transform: scale(1.05);
        }
        .item-card:hover {
            transform: scale(1.02);
        }
        .item-text {
            font-weight: bold;
            font-size: 1.5rem;
            color: #374151;
        }
        #confirm-button {
            pointer-events: none;
        }

        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1.5rem !important;
                border-radius: 1.5rem;
            }
            .mobile-h1 {
                font-size: 2.25rem !important; /* 4xl */
            }
            .mobile-text {
                font-size: 1rem !important; /* base */
            }
            .grid-cols-2-mobile {
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 1rem;
            }
            .item-card {
                padding: 1.5rem;
            }
            .item-text {
                font-size: 1.25rem;
            }
        }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4 sm:p-6">

    <div class="bg-white/70 shadow-2xl rounded-3xl p-8 max-w-xl w-full text-center backdrop-blur-md mobile-card">
        <h1 class="text-4xl font-bold mb-4 mobile-h1 text-gray-800">추천받을 아이템을 선택하세요</h1>
        <p class="text-lg text-gray-700 mb-8 mobile-text">한 가지만 선택 가능합니다</p>
        
        <div class="grid grid-cols-2-mobile md:grid-cols-2 gap-4 md:gap-6 mb-6">
            <div class="item-card" data-item="상의" data-code="001">
                <p class="item-text">👕상의</p>
            </div>
            <div class="item-card" data-item="하의" data-code="003">
                <p class="item-text">👖하의</p>
            </div>
            <div class="item-card" data-item="아우터" data-code="002">
                <p class="item-text">🧥아우터</p>
            </div>
            <div class="item-card" data-item="신발" data-code="103">
                <p class="item-text">👟신발</p>
            </div>
            <div class="item-card" data-item="모자" data-code="101001">
                <p class="item-text">🧢모자</p>
            </div>
            <div class="item-card" data-item="가방" data-code="004">
                <p class="item-text">👜가방</p>
            </div>
        </div>

        <a href="#" id="confirm-button"
            class="w-full inline-block text-center bg-gray-400 text-white text-lg font-bold py-4 px-6 rounded-full
                transition-colors duration-300 focus:outline-none cursor-not-allowed">
            선택 완료
        </a>
    </div>

    <script>
        const itemCards = document.querySelectorAll('.item-card');
        const confirmButton = document.getElementById('confirm-button');
        let selectedItemCode = null;

        itemCards.forEach(card => {
            card.addEventListener('click', () => {
                itemCards.forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                selectedItemCode = card.dataset.code;
                
                confirmButton.classList.add('bg-indigo-600', 'hover:bg-indigo-700', 'hover:scale-105');
                confirmButton.classList.remove('bg-gray-400', 'cursor-not-allowed');
                confirmButton.href = "/loading?item_code=" + selectedItemCode;
                confirmButton.style.pointerEvents = 'auto';
            });
        });

        // 초기 상태 설정
        confirmButton.classList.remove('bg-indigo-600', 'hover:bg-indigo-700', 'hover:scale-105');
        confirmButton.classList.add('bg-gray-400', 'cursor-not-allowed');
        confirmButton.style.pointerEvents = 'none';
    </script>
</body>
</html>
"""
HTML_LOADING_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>상품 추천 중...</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body {
            font-family: 'Noto Sans KR', sans-serif;
            background-color: #f7f7f7;
        }

        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1.5rem !important;
                border-radius: 1.5rem;
            }
            .mobile-h1 {
                font-size: 1.875rem !important; /* 3xl */
            }
            .mobile-text {
                font-size: 1rem !important; /* base */
            }
        }
    </style>
</head>
<body class="flex items-center justify-center min-h-screen p-4 sm:p-6">

    <div class="bg-white/70 p-8 rounded-3xl shadow-2xl max-w-xl w-full backdrop-blur-md mobile-card">
        <div class="relative w-full h-8 bg-gray-200 rounded-lg mb-6 overflow-hidden">
            <div id="progressBar" class="absolute left-0 top-0 h-full w-0 bg-blue-500 transition-all duration-500"></div>
            <span class="absolute inset-0 flex items-center justify-center font-bold text-sm text-gray-800" id="progressText">0%</span>
        </div>

        <h1 class="text-3xl font-bold mb-2 text-gray-800 text-center mobile-h1">추천 상품을 찾는 중입니다...</h1>
        <p class="text-lg text-gray-700 mb-4 text-center mobile-text">잠시만 기다려 주세요.</p>
        <p class="text-sm text-gray-500 text-center">(이 작업은 최대 20초 정도 소요될 수 있습니다)</p>
    </div>

    <script>
        const urlParams = new URLSearchParams(window.location.search);
        const itemCode = urlParams.get('item_code');
        const progressBar = document.getElementById('progressBar');
        const progressText = document.getElementById('progressText');

        // 가짜 진행률 표시
        let progress = 0;
        const interval = setInterval(() => {
            if (progress >= 99) {
                clearInterval(interval);
            } else {
                progress += 1;
                progressBar.style.width = progress + '%';
                progressText.textContent = progress + '%';
            }
        }, 100);

        fetch(`/start_recommendation?item_code=${itemCode}`)
            .then(response => response.json())
            .then(data => {
                progressBar.style.width = '100%';
                progressText.textContent = '100%';
                if (data.redirect) {
                    window.location.href = data.redirect;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('상품 정보를 가져오는 중 오류가 발생했습니다. 다시 시도해주세요.');
                window.location.href = '/select_item';
            });
    </script>
</body>
</html>

"""

HTML_RECOMMENDATIONS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>추천 상품</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;700&display=swap');
        body {
            font-family: 'Noto Sans KR', sans-serif;
            background-color: #f7f7f7;
            color: #374151;
            padding: 0;
        }
        .product-card {
            background-color: #fff;
            border-radius: 0.5rem;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            overflow: hidden;
            text-align: left;
            padding: 1rem;
        }
        .product-image {
            width: 100%;
            height: 15rem;
            object-fit: cover;
            border-radius: 0.25rem;
            margin-bottom: 0.5rem;
        }
        .product-brand {
            font-size: 0.75rem;
            color: #6B7280;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }
        .product-name {
            font-size: 0.875rem;
            color: #1F2937;
            font-weight: 500;
            line-height: 1.25;
            height: 2.5rem;
            overflow: hidden;
            text-overflow: ellipsis;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
        }
        .product-price {
            font-size: 1rem;
            font-weight: 700;
            color: #111827;
            margin-top: 0.5rem;
        }
        .product-buttons {
            display: flex;
            gap: 0.5rem;
            margin-top: 0.75rem;
        }
        .btn {
            flex-grow: 1;
            text-align: center;
            padding: 0.5rem 0.75rem;
            border-radius: 0.5rem;
            font-size: 0.875rem;
            font-weight: 600;
            transition: all 0.2s ease-in-out;
        }
        .btn-link {
            background-color: #E5E7EB;
            color: #4B5563;
        }
        .btn-wishlist {
            background-color: #4C51BF;
            color: #fff;
        }
        .btn-link:hover { background-color: #D1D5DB; }
        .btn-wishlist:hover { background-color: #434190; }

        /* PC (769px 이상) */
        @media (min-width: 769px) {
            body { display: flex; }
            .wishlist-container {
                position: fixed;
                left: 0;
                top: 0;
                height: 100vh;
                width: 320px;
                background-color: #fff;
                box-shadow: 4px 0 10px rgba(0,0,0,0.1);
                z-index: 10;
                padding: 1rem;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                transform: translateX(0); /* 항상 열려 있음 */
            }
            #main-content {
                margin-left: 320px;
                transition: margin-left 0.3s ease-in-out;
            }
            #toggle-wishlist-btn {
                display: none; /* 하트 버튼 숨기기 */
            }
            .wishlist-close-btn {
                display: none; /* PC에서는 X 버튼 숨기기 */
            }
            .wishlist-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }
        }

        /* Mobile (768px 이하) */
        @media (max-width: 768px) {
            body {
                flex-direction: column;
                padding-top: 120px;
            }
            .fixed-header-container {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                z-index: 40;
                background-color: #f7f7f7;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                padding: 1rem;
            }
            .mobile-header-buttons {
                display: flex;
                justify-content: center;
                gap: 0.5rem;
                width: 100%;
                flex-wrap: wrap;
            }
            #wishlist-container {
                position: fixed;
                top: 0;
                left: 0; /* 왼쪽에서 열리도록 변경 */
                width: 320px;
                height: 100%;
                background-color: #fff;
                box-shadow: 4px 0 10px rgba(0,0,0,0.2); /* 그림자 방향 유지 */
                z-index: 50;
                display: flex;
                flex-direction: column;
                padding: 1rem;
                overflow-y: auto;
                transform: translateX(-100%); /* 초기 상태: 왼쪽으로 완전히 숨김 */
                transition: transform 0.3s ease-in-out;
            }
            #wishlist-container.is-open {
                transform: translateX(0); /* 버튼 클릭 시: 원래 위치로 이동 */
            }
            #main-content { margin-left: 0; }
            .top-fixed-header { display: none; } /* PC 헤더 숨기기 */

            #toggle-wishlist-btn {
                display: block; /* 하트 버튼 보이게 하기 */
            }
            .wishlist-close-btn {
                display: block; /* 모바일에서 X 버튼 보이게 하기 */
                background: none;
                border: none;
                color: #6B7280;
                font-size: 1.5rem;
                cursor: pointer;
                padding: 0;
                margin-left: 1rem;
            }
            .wishlist-close-btn:hover {
                color: #4B5563;
            }
            .wishlist-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }
        }

        .wishlist-list { flex-grow: 1; }
        .wishlist-item {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.5rem;
            border-bottom: 1px solid #e5e7eb;
            flex-wrap: nowrap;
        }
        .wishlist-item-content {
            display: flex;
            align-items: center;
            flex-grow: 1;
            gap: 0.75rem;
            overflow: hidden;
            flex-shrink: 1;
        }
        .wishlist-item-info {
            flex-grow: 1;
            overflow: hidden;
            min-width: 0;
        }
        .wishlist-item img {
            width: 60px;
            height: 60px;
            object-fit: cover;
            border-radius: 0.25rem;
        }
        .wishlist-item-name {
            font-size: 0.875rem;
            font-weight: 500;
            line-height: 1.25;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .wishlist-item-price {
            font-size: 0.75rem;
            color: #6B7280;
        }
        .wishlist-item-remove-btn {
            color: #EF4444;
            font-size: 1.2rem;
            cursor: pointer;
            border: none;
            background: none;
            padding: 0;
            margin: 0;
            line-height: 1;
        }
        .quantity-control {
            display: flex;
            align-items: center;
            gap: 0.25rem;
            margin-right: 0.5rem;
            flex-shrink: 0;
        }
        .quantity-control button {
            background-color: #E5E7EB;
            border-radius: 9999px;
            width: 24px;
            height: 24px;
            font-size: 1rem;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #4B5563;
        }
        .wishlist-summary {
            margin-top: 1rem;
            padding-top: 1rem;
            border-top: 2px solid #E5E7EB;
            text-align: right;
            font-weight: bold;
        }
        .wishlist-summary-price {
            font-size: 1.25rem;
            color: #1F2937;
        }
        .wishlist-clear-btn {
            width: 100%;
            background-color: #EF4444;
            color: #fff;
            font-weight: bold;
            padding: 0.75rem;
            border-radius: 0.5rem;
            margin-top: 0.5rem;
            transition: background-color 0.2s;
        }
        .wishlist-clear-btn:hover {
            background-color: #DC2626;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            padding-top: 100px;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgb(0,0,0);
            background-color: rgba(0,0,0,0.9);
        }
        .modal-content {
            margin: auto;
            display: block;
            width: 80%;
            max-width: 700px;
        }
        #modalCaption {
            margin: auto;
            display: block;
            width: 80%;
            max-width: 700px;
            text-align: center;
            color: #ccc;
            padding: 10px 0;
        }
        .modal-close {
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            transition: 0.3s;
            cursor: pointer;
        }
        .modal-close:hover,
        .modal-close:focus {
            color: #bbb;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <button id="toggle-wishlist-btn"
        class="fixed bottom-4 right-4 bg-indigo-500 text-white p-4 rounded-full shadow-lg z-50 hover:bg-indigo-600 transition-colors md:hidden">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-.318-.318a4.5 4.5 0 00-6.364 0z" />
        </svg>
    </button>

    <div class="fixed-header-container md:hidden">
        <div class="text-center">
            <h1 class="text-xl font-bold mb-1 text-gray-800"><span style="color: {{ palette[0] }};">{{ korean_name }}</span>을 위한 {{ item_name }} 추천 상품</h1>
            <p class="text-sm text-gray-500">아래 상품 이미지를 클릭하여 확대해 볼 수 있습니다.  </p>
        </div>
        <div class="mobile-header-buttons mt-4">
            <a href="{{ url_for('select_item') }}"
                class="inline-block bg-gray-500 text-white font-bold py-2 px-4 rounded-full
                        hover:bg-gray-600 transition-colors duration-300 transform hover:scale-105 text-sm">
                뒤로가기
            </a>
            <a href="{{ url_for('index_reset') }}"
                class="inline-block bg-gray-200 text-gray-700 font-bold py-2 px-4 rounded-full
                        hover:bg-gray-300 transition-colors duration-300 transform hover:scale-105 text-sm">
                다시 시작하기
            </a>
        </div>
    </div>

    <div id="wishlist-container" class="wishlist-container">
        <div class="wishlist-header">
            <h2 class="text-xl font-bold">⭐ 위시리스트</h2>
            <button class="wishlist-close-btn" onclick="closeWishlist()">×</button>
        </div>
        <div class="wishlist-list flex-grow" id="wishlist-list">
            {% if wishlist_items %}
                {% for item in wishlist_items %}
                <div class="wishlist-item" data-id="{{ item['id'] }}">
                    <div class="wishlist-item-content">
                        <img src="{{ item['img_url'] }}" alt="{{ item['name'] }}">
                        <div class="wishlist-item-info">
                            <p class="wishlist-item-brand text-xs text-gray-500 font-semibold">{{ item['brand'] }}</p>
                            <p class="wishlist-item-name">{{ item['name'] }}</p>
                            <p class="wishlist-item-price">{{ item['price'] }}</p>
                        </div>
                    </div>
                    <div class="quantity-control">
                        <button onclick="updateQuantity('{{ item['id'] }}', -1)">-</button>
                        <span>{{ item['quantity'] }}</span>
                        <button onclick="updateQuantity('{{ item['id'] }}', 1)">+</button>
                    </div>
                    <button class="wishlist-item-remove-btn" onclick="removeFromWishlist('{{ item['id'] }}')">×</button>
                </div>
                {% endfor %}
            {% else %}
                <p class="text-sm text-gray-500 text-center">위시리스트가 비어있습니다.</p>
            {% endif %}
        </div>
        <div class="wishlist-summary" id="wishlist-summary">
            총 금액 : <span class="wishlist-summary-price">{{ total_price }}원</span>
        </div>
        <a href="{{ url_for('email_page') }}"
            class="w-full inline-block bg-indigo-500 text-white font-bold py-3 px-4 rounded-md
                    hover:bg-indigo-600 transition-colors mt-4 text-center">
                    이메일로 전송
        </a>
        <button class="wishlist-clear-btn" onclick="clearWishlist()">전체 삭제</button>
    </div>

    <div class="flex-1" id="main-content">
        <div class="top-fixed-header hidden md:block">
            <div class="text-center mb-4">
                <h1 class="text-3xl font-bold text-gray-800"><span style="color: {{ palette[0] }};">{{ korean_name }}</span>을 위한 {{ item_name }} 추천 상품</h1>
                <p class="text-sm text-gray-500">아래 상품을 클릭하면 구매 페이지로 이동합니다.</p>
            </div>
            <div class="flex justify-end gap-4">
                <a href="{{ url_for('select_item') }}"
                    class="inline-block bg-gray-500 text-white font-bold py-3 px-6 rounded-full
                           hover:bg-gray-600 transition-colors duration-300 transform hover:scale-105">
                    다른 카테고리 보러가기
                </a>
                <a href="{{ url_for('index_reset') }}"
                    class="inline-block bg-gray-200 text-gray-700 font-bold py-3 px-6 rounded-full
                           hover:bg-gray-300 transition-colors duration-300 transform hover:scale-105">
                    다시 시작하기
                </a>
            </div>
        </div>

        <div class="main-content-wrapper p-4 md:p-0">
            <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-4 gap-4 md:gap-6 mt-4">
                {% for product in products %}
                    <div class="product-card">
                        <a href="#" class="image-modal-trigger block">
                            <img src="{{ product['img_url'] }}" alt="{{ product['name'] }}" class="product-image">
                        </a>
                        <a href="{{ product['url'] }}" target="_blank" class="block">
                            <p class="product-brand">{{ product['brand'] }}</p>
                            <p class="product-name">{{ product['name'] }}</p>
                            <p class="product-price">{{ product['price'] }}</p>
                        </a>
                        <div class="product-buttons">
                            <a href="{{ product['url'] }}" target="_blank" class="btn btn-link">상품보러가기</a>
                            <button class="btn btn-wishlist"
                                    onclick="addToWishlist('{{ product['brand'] | e }}', '{{ product['name'] | e }}', '{{ product['price'] | e }}', '{{ product['img_url'] | e }}', '{{ product['url'] | e }}')">
                                위시리스트에 담기
                            </button>
                        </div>
                    </div>
                {% endfor %}
                {% if not products %}
                <p class="col-span-full text-red-500 text-lg">⚠️ 상품 정보를 가져올 수 없습니다.</p>
                <p class="col-span-full text-gray-500 text-sm">무신사 웹사이트의 구조가 변경되었거나, 접속이 차단되었을 수 있습니다.</p>
                {% endif %}
            </div>
        </div>
    </div>

    <div id="imageModal" class="modal">
        <span class="modal-close">&times;</span>
        <img class="modal-content" id="modalImage">
        <div id="modalCaption"></div>
    </div>

    <script>
        function addToWishlist(brand, name, price, img_url, url) {
            const product = {
                brand: brand,
                name: name,
                price: price,
                img_url: img_url,
                url: url
            };
            fetch('/add_to_wishlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(product)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateWishlistUI(data.wishlist);
                } else {
                    alert('위시리스트에 상품을 추가하는 데 실패했습니다.');
                }
            })
            .catch(error => console.error('Error:', error));
        }

        function updateQuantity(id, delta) {
            fetch('/update_wishlist_quantity', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id, delta: delta })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateWishlistUI(data.wishlist);
                } else {
                    alert('수량 변경에 실패했습니다.');
                }
            })
            .catch(error => console.error('Error:', error));
        }

        function removeFromWishlist(id) {
            fetch('/remove_from_wishlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: id })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateWishlistUI(data.wishlist);
                } else {
                    alert('위시리스트에서 상품을 삭제하는 데 실패했습니다.');
                }
            })
            .catch(error => console.error('Error:', error));
        }

        function clearWishlist() {
            fetch('/clear_wishlist', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateWishlistUI(data.wishlist);
                } else {
                    alert('위시리스트를 비우는 데 실패했습니다.');
                }
            })
            .catch(error => console.error('Error:', error));
        }

        function updateWishlistUI(wishlist) {
            const wishlistList = document.getElementById('wishlist-list');
            const totalSummary = document.getElementById('wishlist-summary');

            if (!wishlistList || !totalSummary) return;

            wishlistList.innerHTML = '';
            let totalPrice = 0;
            if (wishlist.length === 0) {
                wishlistList.innerHTML = '<p class="text-sm text-gray-500 text-center">위시리스트가 비어있습니다.</p>';
            } else {
                wishlist.forEach(product => {
                    const price = parseInt(product.price.replace(/,/g, '').replace('원', ''));
                    totalPrice += price * product.quantity;
                    const wishlistHtml = `
                        <div class="wishlist-item" data-id="${product.id}">
                            <div class="wishlist-item-content">
                                <img src="${product.img_url}" alt="${product.name}">
                                <div class="wishlist-item-info">
                                    <p class="wishlist-item-brand text-xs text-gray-500 font-semibold">${product.brand}</p>
                                    <p class="wishlist-item-name">${product.name}</p>
                                    <p class="wishlist-item-price">${product.price}</p>
                                </div>
                            </div>
                            <div class="quantity-control">
                                <button onclick="updateQuantity('${product.id}', -1)">-</button>
                                <span>${product.quantity}</span>
                                <button onclick="updateQuantity('${product.id}', 1)">+</button>
                            </div>
                            <button class="wishlist-item-remove-btn" onclick="removeFromWishlist('${product.id}')">×</button>
                        </div>
                    `;
                    wishlistList.innerHTML += wishlistHtml;
                });
            }
            totalSummary.innerHTML = `총 금액 : <span class="wishlist-summary-price">${totalPrice.toLocaleString()}원</span>`;
        }
        
        // 추가된 함수: 위시리스트를 닫는 기능
        function closeWishlist() {
            const wishlistContainer = document.getElementById('wishlist-container');
            if (wishlistContainer) {
                wishlistContainer.classList.remove('is-open');
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            const modal = document.getElementById('imageModal');
            const modalImg = document.getElementById("modalImage");
            const captionText = document.getElementById("modalCaption");
            const triggers = document.querySelectorAll('.image-modal-trigger');

            const toggleWishlistBtn = document.getElementById('toggle-wishlist-btn');
            const wishlistContainer = document.getElementById('wishlist-container');
            if (toggleWishlistBtn && wishlistContainer) {
                toggleWishlistBtn.addEventListener('click', () => {
                    wishlistContainer.classList.toggle('is-open');
                });
            }

            triggers.forEach(trigger => {
                trigger.addEventListener('click', (event) => {
                    event.preventDefault();
                    const img = event.target.closest('.image-modal-trigger').querySelector('.product-image');
                    modal.style.display = "block";
                    modalImg.src = img.src;
                    captionText.innerHTML = img.alt;
                });
            });

            const span = document.getElementsByClassName("modal-close")[0];
            span.onclick = () => {
                modal.style.display = "none";
            };

            window.onclick = (event) => {
                if (event.target === modal) {
                    modal.style.display = "none";
                }
            };
        });
    </script>
</body>
</html>
"""

HTML_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>추천 상품 이메일</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* 로딩 오버레이 스타일 */
        #loadingOverlay {
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.6);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 9999;
        }
        .loader {
            border: 12px solid #f3f3f3;
            border-top: 12px solid #3498db;
            border-radius: 50%;
            width: 120px;
            height: 120px;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1.5rem !important;
                border-radius: 1.5rem;
            }
            .mobile-h2 {
                font-size: 1.5rem !important; /* 2xl */
            }
            .mobile-text {
                font-size: 0.875rem !important; /* sm */
            }
            .email-input {
                width: 100% !important;
            }
        }
    </style>
</head>
<body class="bg-gradient-to-r from-blue-100 via-blue-50 to-white flex items-center justify-center min-h-screen p-4 sm:p-6">

    <div class="bg-white shadow-xl rounded-2xl p-8 w-full max-w-xl mobile-card">
        <h2 class="text-2xl font-bold mb-4 text-center text-blue-600 mobile-h2">💌 이메일로 위시리스트 전송</h2>
        <p class="text-center text-gray-600 mb-4 mobile-text">원하는 이메일 주소를 입력하고 전송 버튼을 눌러주세요.</p>
        <form id="emailForm" method="POST" action="/email_page" class="space-y-4">
            <input type="email" name="email" placeholder="example@gmail.com" required
                    class="w-full mx-auto block p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-400 email-input">
            <button type="submit"
                    class="w-full mx-auto block bg-blue-600 hover:bg-blue-600 text-white font-bold py-3 rounded-lg transition-colors text-base">
                이메일 전송
            </button>
        </form>
        <a href="{{ url_for('show_recommendations') }}" class="block mt-4 text-center text-gray-500 hover:underline text-sm">뒤로가기</a>
    </div>

    <div id="loadingOverlay">
        <div class="loader"></div>
    </div>

    <script>
        document.getElementById("emailForm").addEventListener("submit", function () {
            // 로딩 오버레이 표시
            document.getElementById("loadingOverlay").style.display = "flex";
        });
    </script>
</body>
</html>

"""


HTML_EMAIL_SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>이메일 전송 완료</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        /* 모바일 최적화 */
        @media (max-width: 640px) {
            .mobile-card {
                padding: 1.5rem !important;
                border-radius: 1.5rem;
            }
            .mobile-h1 {
                font-size: 2rem !important; /* 3xl */
            }
            .mobile-text {
                font-size: 0.875rem !important; /* sm */
            }
            .mobile-btn {
                font-size: 1rem !important;
                padding: 0.75rem 1.5rem !important;
            }
        }
    </style>
</head>
<body class="bg-gradient-to-r from-green-100 via-green-50 to-white flex items-center justify-center min-h-screen p-4 sm:p-6">
    <div class="bg-white shadow-xl rounded-2xl p-8 w-full max-w-xl text-center mobile-card">
        <img src="https://cdn-icons-png.flaticon.com/512/190/190411.png" alt="success" class="w-20 mx-auto mb-4">
        <h1 class="text-3xl font-bold text-green-600 mb-4 mobile-h1">🚀 전송 완료!</h1>
        <p class="text-base text-gray-600 mb-6 mobile-text">입력하신 이메일 주소로 추천 상품 위시리스트가 전송되었습니다.</p>
        <a href="{{ url_for('show_recommendations') }}" 
           class="inline-block bg-green-500 hover:bg-green-600 text-white font-bold py-3 px-6 text-base rounded-lg transition-colors mobile-btn">
            돌아가기
        </a>
    </div>
</body>
</html>
"""

# --- Flask 라우트 및 함수 ---

import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)

@app.before_request
def make_session_permanent():
    session.permanent = True

    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

@app.route('/')
def index():
    if 'user_id' not in session:
        session.clear()
    return render_template_string(HTML_START_TEMPLATE)
    
@app.route('/index_reset')
def index_reset():
    session.clear()
    return redirect(url_for('index'))

@app.route('/select_gender')
def select_gender():
    return render_template_string(HTML_SELECT_GENDER_TEMPLATE)

@app.route('/upload_page')
def upload_page():
    gender = request.args.get('gender', 'female')
    session['gender'] = gender
    return render_template_string(HTML_UPLOAD_TEMPLATE, gender=gender)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('upload_page'))
    
    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('upload_page'))

    if file:
        try:
            image_bytes = file.read()
            
            # 1. Rekognition으로 얼굴 감지
            rekognition_client = boto3.client('rekognition')
            response = rekognition_client.detect_faces(Image={'Bytes': image_bytes}, Attributes=['ALL'])
            
            if not response['FaceDetails']:
                return render_template_string("<html><body><p>이미지에서 얼굴을 찾을 수 없습니다.</p><a href='/upload_page'>다시 시도</a></body></html>")
            
            face_detail = response['FaceDetails'][0]
            box = face_detail['BoundingBox']
            
            # 2. Pillow로 얼굴 크롭
            img = Image.open(io.BytesIO(image_bytes))
            img_width, img_height = img.size
            
            left = img_width * box['Left']
            top = img_height * box['Top']
            width = img_width * box['Width']
            height = img_height * box['Height']
            
            cropped_image = img.crop((left, top, left + width, top + height))

            # 3. 크롭된 이미지를 메모리 버퍼에 저장하고 세션에 키를 저장
            buf = io.BytesIO()
            cropped_image.save(buf, format='JPEG')
            unique_key = str(uuid.uuid4())
            image_cache[unique_key] = buf.getvalue()
            session['cropped_face_key'] = unique_key
            
            # 4. ✨ 변형된 부분: 크롭된 이미지로 퍼스널 컬러 분석
            #    Pillow 이미지를 OpenCV(Numpy) 형식으로 변환
            #    (cv2.imdecode와 기존 `image` 변수 사용 코드를 아래 코드로 대체합니다)
            cropped_image_np = np.array(cropped_image)
            
            # 크롭된 이미지의 중앙에서 피부 패치 추출
            h, w, _ = cropped_image_np.shape
            center_x, center_y = h // 2, w // 2
            skin_patch = cropped_image_np[center_x - 25:center_x + 25, center_y - 25:center_y + 25]
            
            # 5. 기존의 퍼스널 컬러 분석 로직은 그대로 사용
            hsv_patch = cv2.cvtColor(skin_patch, cv2.COLOR_RGB2HSV) # RGB2HSV로 변경 (Pillow는 RGB를 사용)
            hue_values = hsv_patch[:,:,0]
            saturation_values = hsv_patch[:,:,1]
            value_values = hsv_patch[:,:,2]
            
            average_hue = np.mean(hue_values)
            average_saturation = np.mean(saturation_values)
            average_value = np.mean(value_values)
            
            if average_hue <= 25:
                if average_saturation >= 60 and average_value >= 120:
                    result = "봄웜"
                else:
                    result = "가을웜"
            else:
                if average_saturation >= 60 and average_value >= 120:
                    result = "겨울쿨"
                else:
                    result = "여름쿨"
            
            session['personal_color'] = result
            
            return redirect(url_for('show_result_page'))
            
            
        except Exception as e:
            return f"오류 발생: {e}"
    else:
        # GET 요청인 경우 upload_page로 리디렉션
        return redirect(url_for('upload_page'))
    
    
# 캐시에 저장된 이미지의 키를 제공하는 함수
# 이 라우트는 HTML의 <img src="..."> 태그가 호출합니다.
@app.route('/get_cropped_image/<string:image_key>')
def get_cropped_image(image_key):
    # 캐시에서 이미지 데이터 가져오기
    image_data = image_cache.get(image_key)
    if image_data is None:
        return "Image not found", 404
        
    # 메모리에서 이미지 데이터를 직접 전송
    return send_file(io.BytesIO(image_data), mimetype='image/jpeg')


# 크롭된 이미지URL을 불러오는 코드
@app.route('/result')
def show_result_page():
    # 세션에서 퍼스널 컬러와 이미지 '키'를 가져옵니다.
    result_data = personal_color_data.get(session.get('personal_color'))
    cropped_image_key = session.get('cropped_face_key')
    
    if not result_data or not cropped_image_key:
        return redirect(url_for('upload_page'))
        
    # HTML 템플릿에 이미지 URL을 전달합니다.
    image_url = url_for('get_cropped_image', image_key=cropped_image_key)
    
    return render_template_string(HTML_RESULT_TEMPLATE, data=result_data, cropped_image_url=image_url)


# 새롭게 추가된 라우트
@app.route('/select_item')
def select_item():
    if 'personal_color' not in session or 'gender' not in session:
        return redirect(url_for('index'))
    return render_template_string(HTML_SELECT_ITEM_TEMPLATE)

# 로딩 페이지 라우트 추가
@app.route('/loading')
def loading():
    item_code = request.args.get('item_code')
    if not item_code:
        return redirect(url_for('select_item'))
    
    # 세션에 item_code 저장
    session['item_code'] = item_code
    return render_template_string(HTML_LOADING_TEMPLATE)

# API 엔드포인트: 비동기적으로 크롤링을 시작하고 결과를 반환
@app.route('/start_recommendation')
def start_recommendation():
    personal_color = session.get('personal_color')
    gender = session.get('gender')
    item_code = session.get('item_code')
    
    if not personal_color or not gender or not item_code:
        return jsonify(redirect=url_for('index'))

    # 크롤링 함수 호출
    recommended_products = crawl_with_selenium(personal_color, gender, item_code)
    
    # 결과를 세션에 저장 (나중에 템플릿에서 사용하기 위해)
    session['recommended_products'] = recommended_products
    
    # 성공적으로 완료되면 결과 페이지로 리다이렉션할 URL 반환
    return jsonify(redirect=url_for('show_recommendations'))

# 최종 결과 페이지 라우트 (GET 요청만 허용)
@app.route('/show_recommendations')
def show_recommendations():
    personal_color = session.get('personal_color')
    recommended_products = session.get('recommended_products')
    user_id = session.get('user_id')

    if not personal_color or recommended_products is None or not user_id:
        return redirect(url_for('index'))

    item_name_map = {
        '001': '상의',
        '003': '하의',
        '002': '아우터',
        '103': '신발',
        '101001': '모자',
        '004': '가방'
    }

    item_code = session.get('item_code')
    item_name = item_name_map.get(item_code, '알 수 없는')

    wishlist_items = server_wishlists.get(user_id, [])

    total_price = 0
    for item in wishlist_items:
        try:
            price_str = item.get('price', '0원').replace(',', '').replace('원', '')
            total_price += int(price_str) * item.get('quantity', 1)
        except (ValueError, TypeError):
            continue

    korean_name = personal_color_data[personal_color]['korean_name']
    palette = personal_color_data[personal_color]['palette']

    return render_template_string(HTML_RECOMMENDATIONS_TEMPLATE, 
                                 products=recommended_products, 
                                 korean_name=korean_name,
                                 palette=palette, 
                                 item_name=item_name, 
                                 wishlist_items=wishlist_items, 
                                 total_price=f'{total_price:,}')
    
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/add_to_wishlist', methods=['POST'])
def add_to_wishlist():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'User not identified.'}), 400

    product_data = request.json
    wishlist = server_wishlists.get(user_id, [])

    found_item = None
    for item in wishlist:
        if item.get('name') == product_data.get('name') and item.get('img_url') == product_data.get('img_url'):
            found_item = item
            break
    
    if found_item:
        found_item['quantity'] += 1
    else:
        product_data['id'] = str(uuid.uuid4())
        product_data['quantity'] = 1
        wishlist.append(product_data)
        
    server_wishlists[user_id] = wishlist
    
    return jsonify({'success': True, 'wishlist': wishlist})


@app.route('/update_wishlist_quantity', methods=['POST'])
def update_wishlist_quantity():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'User not identified.'}), 400

    data = request.json
    product_id = data.get('id')
    delta = data.get('delta')
    
    wishlist = server_wishlists.get(user_id, [])
    
    for item in wishlist:
        if item.get('id') == product_id:
            item['quantity'] += delta
            if item['quantity'] <= 0:
                wishlist.remove(item)
            break
            
    server_wishlists[user_id] = wishlist
    return jsonify({'success': True, 'wishlist': wishlist})


@app.route('/remove_from_wishlist', methods=['POST'])
def remove_from_wishlist():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'User not identified.'}), 400

    product_id = request.json.get('id')
    wishlist = server_wishlists.get(user_id, [])
    wishlist = [item for item in wishlist if item.get('id') != product_id]

    server_wishlists[user_id] = wishlist
    return jsonify({'success': True, 'wishlist': wishlist})
    
@app.route('/clear_wishlist', methods=['POST'])
def clear_wishlist():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'User not identified.'}), 400

    server_wishlists[user_id] = []
    return jsonify({'success': True, 'wishlist': []})

@app.route('/email_page', methods=['GET', 'POST'])
def email_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        wishlist_items = server_wishlists.get(user_id, [])

        total_price = 0
        for item in wishlist_items:
            price_str = item['price']
            price_num = int(''.join(filter(str.isdigit, price_str)))
            total_price += price_num * int(item.get('quantity', 1))

        total_count = sum(int(item.get('quantity', 1)) for item in wishlist_items)

        html_body = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <title>추천 상품 위시리스트</title>
        </head>
        <body style="font-family: 'Noto Sans KR', sans-serif; background-color: #f7f7f7; margin:0; padding:20px;">
            <table align="center" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff; border-radius:10px; overflow:hidden; max-width: 100%;">
                <tr>
                    <td style="padding:20px; text-align:center; background-color:#4f46e5; color:#ffffff; font-size:24px; font-weight:bold;">
                        💌 추천 상품 위시리스트
                    </td>
                </tr>
        """

        for item in wishlist_items:
            html_body += f"""
                <tr>
                    <td style="padding:15px; border-bottom:1px solid #e5e7eb;">
                        <table width="100%" cellpadding="0" cellspacing="0">
                            <tr>
                                <td width="100" style="padding-right:15px;">
                                    <img src="{item['img_url']}" width="80" height="80" style="border-radius:8px; object-fit:cover;">
                                </td>
                                <td style="vertical-align:top;">
                                    <p style="margin:0; font-size:13px; font-weight:bold; color:#4b5563;">{item.get('brand', '')}</p>
                                    <p style="margin:0; font-size:16px; font-weight:bold; color:#111827;">{item['name']}</p>
                                    <p style="margin:5px 0; font-size:14px; font-weight:bold; color:#ef4444;">{item['price']} × {item.get('quantity',1)}</p>
                                    <a href="{item['url']}" target="_blank" style="display:inline-block; padding:6px 12px; font-size:14px; color:#ffffff; background-color:#4f46e5; border-radius:5px; text-decoration:none;">상품 보러가기</a>
                                </td>
                            </tr>
                        </table>
                    </td>
                </tr>
            """

        html_body += f"""
            <tr>
                <td style="padding:20px; background-color:#f9fafb; text-align:center;">
                    <table style="width:100%; max-width:600px; margin:0 auto; border-collapse:collapse; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 3px 10px rgba(0,0,0,0.05);">
                        <tr>
                            <td style="padding:15px 20px; border-bottom:1px solid #e5e7eb; font-size:22px; font-weight:bold; color:#111827; background:#f3f4f6;">
                                📦 Total
                            </td>
                        </tr>
                        <tr>
                            <td style="padding:15px 20px; font-size:22px; color:#374151; text-align:left;">
                                <ul style="list-style:none; padding:0; margin:0;">
                                    <li style="margin:8px 0; display:flex; justify-content:space-between;">
                                        <span style="font-weight:bold;">총 상품 개수</span>
                                        <span style="font-weight:bold; color:#111827;">{total_count} 개</span>
                                    </li>
                                    <li style="margin:8px 0; display:flex; justify-content:space-between;">
                                        <span style="font-weight:bold;">총 금액</span>
                                        <span style="font-weight:bold; color:#4f46e5;">{total_price:,} 원</span>
                                    </li>
                                </ul>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
            <tr>
                <td style="padding:15px; text-align:center; font-size:14px; color:#9ca3af;">
                    이 이메일은 자동 발송되었습니다.
                </td>
            </tr>
            </table>
        </body>
        </html>
        """

        sender_email = "johnjung51@gmail.com"
        sender_password = "gqcn qead dotb cehe"
        receiver_email = email

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = "추천 상품 위시리스트"
        msg.attach(MIMEText(html_body, 'html'))

        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
            server.quit()
            return render_template_string(HTML_EMAIL_SUCCESS_TEMPLATE)
        except Exception as e:
            return f"이메일 전송 실패: {str(e)}"

    return render_template_string(HTML_EMAIL_TEMPLATE)

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)