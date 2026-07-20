#!/usr/bin/env python3
"""
Download and import data from the Gaokao-Compass-11M HuggingFace dataset.
Focused on: Guangdong major scores + all provinces' school-admission/score-range.
"""
import csv
import sqlite3
import time
import urllib.request
import urllib.error
import os
import sys
import re
from pathlib import Path

DB_PATH = "data/zhinan.db"
BASE_URL = "https://huggingface.co/datasets/zifeiren/Gaokao-Compass-11M/resolve/main/data"

# Map province names between dataset and our DB
PROVINCE_MAP = {
    'anhui': '安徽', 'beijing': '北京', 'chongqing': '重庆', 'fujian': '福建',
    'gansu': '甘肃', 'guangdong': '广东', 'guangxi': '广西', 'guizhou': '贵州',
    'hainan': '海南', 'hebei': '河北', 'heilongjiang': '黑龙江', 'henan': '河南',
    'hubei': '湖北', 'hunan': '湖南', 'jiangsu': '江苏', 'jiangxi': '江西',
    'jilin': '吉林', 'liaoning': '辽宁', 'neimenggu': '内蒙古', 'ningxia': '宁夏',
    'qinghai': '青海', 'shaanxi': '陕西', 'shandong': '山东', 'shanghai': '上海',
    'shanxi': '山西', 'sichuan': '四川', 'tianjin': '天津', 'xinjiang': '新疆',
    'xizang': '西藏', 'yunnan': '云南', 'zhejiang': '浙江',
}

CATEGORY_MAP = {
    '物理类': '物理', '历史类': '历史', '理科': '物理', '文科': '历史',
    '综合': '综合', '物理': '物理', '历史': '历史',
}

def download_csv(url, retries=3):
    """Download a CSV file from URL."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/csv,text/plain,*/*',
                }
            )
            resp = urllib.request.urlopen(req, timeout=60)
            content = resp.read()
            # Check if it's actually a redirect or error page
            if len(content) < 100 and b'<!DOCTYPE' in content:
                print(f"  WARNING: Got HTML page instead of CSV (size={len(content)})", file=sys.stderr)
                return None
            return content
        except Exception as e:
            print(f"  Download attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(3)
    return None


def import_school_admission(conn, csv_content, year, province_en, province_cn):
    """Import school-level admission data (投档线)."""
    if not csv_content or len(csv_content) < 50:
        return 0
    
    text = csv_content.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(text.splitlines())
    
    cursor = conn.cursor()
    inserted = 0
    skipped = 0
    batch_count = 0
    
    for row in reader:
        uni_name = row.get('university_name', '').strip()
        category = row.get('category', '').strip()
        batch = row.get('batch', '').strip()
        min_score = row.get('min_score', '').strip()
        min_rank = row.get('min_rank', '').strip()
        
        if not uni_name or not min_score:
            continue
        
        # Find school in DB
        cursor.execute('SELECT id FROM schools WHERE name = ?', (uni_name,))
        school = cursor.fetchone()
        if not school:
            # Try fuzzy match
            cursor.execute('SELECT id FROM schools WHERE name LIKE ?', (f'%{uni_name}%',))
            school = cursor.fetchone()
        if not school:
            skipped += 1
            continue
        
        school_id = school[0]
        
        # Determine subject type
        subject_type = CATEGORY_MAP.get(category, category)
        
        # Build batch info
        batch_name = f"{batch}_{subject_type}" if batch else f"本科批_{subject_type}"
        
        min_score_val = int(float(min_score)) if min_score else None
        min_rank_val = int(float(min_rank)) if min_rank else None
        
        # Check if record exists
        cursor.execute(
            'SELECT id FROM admission_scores WHERE school_id=? AND year=? AND province=? AND batch=? AND min_score=?',
            (school_id, year, province_cn, batch_name, min_score_val)
        )
        if cursor.fetchone():
            skipped += 1
            continue
        
        cursor.execute(
            '''INSERT INTO admission_scores (school_id, year, province, batch, min_score, min_rank)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (school_id, year, province_cn, batch_name, min_score_val, min_rank_val)
        )
        inserted += 1
        batch_count += 1
    
    conn.commit()
    return inserted


def import_major_admission(conn, csv_content, year, province_cn):
    """Import major-level admission data (专业分数)."""
    if not csv_content or len(csv_content) < 50:
        return 0
    
    text = csv_content.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(text.splitlines())
    
    cursor = conn.cursor()
    inserted = 0
    skipped = 0
    
    for row in reader:
        uni_name = row.get('university_name', '').strip()
        major_name = row.get('major_name', '').strip()
        category = row.get('category', '').strip()
        batch = row.get('batch', '').strip()
        min_score = row.get('min_score', '').strip()
        min_rank = row.get('min_rank', '').strip()
        max_score = row.get('max_score', '').strip()
        avg_score = row.get('avg_score', '').strip()
        
        if not uni_name or not major_name or not min_score:
            continue
        if not min_score.isdigit():
            continue
        
        # Find school
        cursor.execute('SELECT id FROM schools WHERE name = ?', (uni_name,))
        school = cursor.fetchone()
        if not school:
            cursor.execute('SELECT id FROM schools WHERE name LIKE ?', (f'%{uni_name}%',))
            school = cursor.fetchone()
        if not school:
            skipped += 1
            continue
        
        school_id = school[0]
        
        # Find major
        cursor.execute('SELECT id FROM majors WHERE name = ?', (major_name,))
        major = cursor.fetchone()
        if not major:
            # Try fuzzy
            cursor.execute('SELECT id FROM majors WHERE name LIKE ?', (f'%{major_name}%',))
            major = cursor.fetchone()
        major_id = major[0] if major else None
        
        subject_type = CATEGORY_MAP.get(category, category)
        
        min_score_val = int(float(min_score))
        max_score_val = int(float(max_score)) if max_score else None
        avg_score_val = float(avg_score) if avg_score else None
        min_rank_val = int(float(min_rank)) if min_rank else None
        
        batch_name = f"{batch}_{subject_type}" if batch else f"本科批_{subject_type}"
        
        # Check duplicate
        cursor.execute(
            'SELECT id FROM admission_scores WHERE school_id=? AND major_id=? AND year=? AND province=? AND batch=? AND min_score=?',
            (school_id, major_id, year, province_cn, batch_name, min_score_val)
        )
        if cursor.fetchone():
            skipped += 1
            continue
        
        cursor.execute(
            '''INSERT INTO admission_scores 
               (school_id, major_id, year, province, batch, min_score, min_rank, max_score, avg_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (school_id, major_id, year, province_cn, batch_name, min_score_val, min_rank_val, max_score_val, avg_score_val)
        )
        inserted += 1
        
        # Commit in batches
        if inserted % 500 == 0:
            conn.commit()
    
    conn.commit()
    return inserted


def import_score_range(conn, csv_content, year, province_cn):
    """Import score-ranking table (一分一段表)."""
    if not csv_content or len(csv_content) < 50:
        return 0
    
    text = csv_content.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(text.splitlines())
    
    cursor = conn.cursor()
    inserted = 0
    
    for row in reader:
        category = row.get('category', '').strip()
        score = row.get('score', '').strip()
        cumulative = row.get('cumulative_count', '').strip()
        segment = row.get('segment_count', '').strip()
        
        if not score or not score.isdigit() or not cumulative or not cumulative.isdigit():
            continue
        
        subject_type = CATEGORY_MAP.get(category, category)
        score_val = int(score)
        rank_val = int(cumulative)
        
        # Check duplicate
        cursor.execute(
            'SELECT id FROM rank_score_tables WHERE year=? AND province=? AND subject_type=? AND score=?',
            (year, province_cn, subject_type, score_val)
        )
        if cursor.fetchone():
            continue
        
        cursor.execute(
            '''INSERT INTO rank_score_tables (year, province, subject_type, score, rank)
               VALUES (?, ?, ?, ?, ?)''',
            (year, province_cn, subject_type, score_val, rank_val)
        )
        inserted += 1
        
        if inserted % 300 == 0:
            conn.commit()
    
    conn.commit()
    return inserted


def main():
    conn = sqlite3.connect(DB_PATH)
    
    total_major = 0
    total_school = 0
    total_rank = 0
    
    # ================================================================
    # 1. GUANGDONG MAJOR DATA (2022 has 本科批 data)
    # ================================================================
    print("=== Guangdong 2022 Major Admission ===")
    url = f"{BASE_URL}/2022/guangdong/major-admission.csv?download=1"
    csv_content = download_csv(url)
    if csv_content:
        count = import_major_admission(conn, csv_content, 2022, '广东')
        print(f"  Imported: {count} records")
        total_major += count
    else:
        print(f"  FAILED to download")
    
    # ================================================================
    # 2. GUANGDONG SCHOOL ADMISSION (2022-2024)
    # ================================================================
    print("\n=== Guangdong School Admission ===")
    for year in [2022, 2023, 2024]:
        print(f"  Year {year}:")
        url = f"{BASE_URL}/{year}/guangdong/school-admission.csv?download=1"
        csv_content = download_csv(url)
        if csv_content:
            count = import_school_admission(conn, csv_content, year, 'guangdong', '广东')
            print(f"    Imported: {count} records")
            total_school += count
        time.sleep(2)
    
    # ================================================================
    # 3. GUANGDONG RANK SCORE (2022-2024) - 一分一段表
    # ================================================================
    print("\n=== Guangdong Score-Range ===")
    for year in [2022, 2023, 2024]:
        print(f"  Year {year}:")
        url = f"{BASE_URL}/{year}/guangdong/score-range.csv?download=1"
        csv_content = download_csv(url)
        if csv_content:
            count = import_score_range(conn, csv_content, year, '广东')
            print(f"    Imported: {count} records")
            total_rank += count
        time.sleep(2)
    
    # ================================================================
    # 4. OTHER PROVINCES DATA
    #   Priority: Beijing, Shanghai, Zhejiang, Jiangsu, Sichuan, 
    #             Henan, Shandong (2024 school-admission + score-range)
    # ================================================================
    priority_provinces = [
        'beijing', 'shanghai', 'zhejiang', 'jiangsu', 'sichuan',
        'henan', 'shandong', 'hubei', 'hunan', 'anhui',
        'fujian', 'shaanxi', 'chongqing', 'liaoning', 'hebei',
    ]
    
    print("\n=== Other Provinces School Admission (2024) ===")
    for prov_en in priority_provinces:
        prov_cn = PROVINCE_MAP.get(prov_en, prov_en)
        print(f"  {prov_cn} (2024):")
        url = f"{BASE_URL}/2024/{prov_en}/school-admission.csv?download=1"
        csv_content = download_csv(url)
        if csv_content:
            count = import_school_admission(conn, csv_content, 2024, prov_en, prov_cn)
            print(f"    School admission: {count} records")
            total_school += count
        time.sleep(2)
    
    print("\n=== Other Provinces Score-Range (2024) ===")
    for prov_en in priority_provinces:
        prov_cn = PROVINCE_MAP.get(prov_en, prov_en)
        print(f"  {prov_cn} (2024):")
        url = f"{BASE_URL}/2024/{prov_en}/score-range.csv?download=1"
        csv_content = download_csv(url)
        if csv_content:
            count = import_score_range(conn, csv_content, 2024, prov_cn)
            print(f"    Score-range: {count} records")
            total_rank += count
        time.sleep(2)
    
    # ================================================================
    # 5. ZHEJIANG AND JIANGSU MAJOR DATA (2024 has 本科批)
    # ================================================================
    print("\n=== Other Provinces Major Admission (2024) ===")
    for prov_en in ['zhejiang', 'jiangsu', 'sichuan', 'shandong', 'henan']:
        prov_cn = PROVINCE_MAP.get(prov_en, prov_en)
        print(f"  {prov_cn} (2024):")
        url = f"{BASE_URL}/2024/{prov_en}/major-admission.csv?download=1"
        csv_content = download_csv(url)
        if csv_content:
            count = import_major_admission(conn, csv_content, 2024, prov_cn)
            print(f"    Major admission: {count} records")
            total_major += count
        time.sleep(2)
    
    # ================================================================
    # SUMMARY
    # ================================================================
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM admission_scores')
    total_as = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM rank_score_tables')
    total_rs = cursor.fetchone()[0]
    
    print(f"\n{'='*60}")
    print(f"IMPORT COMPLETE")
    print(f"{'='*60}")
    print(f"New major records:     {total_major}")
    print(f"New school records:    {total_school}")
    print(f"New rank-score records: {total_rank}")
    print(f"Total admission_scores: {total_as}")
    print(f"Total rank_score_tables: {total_rs}")
    
    conn.close()

if __name__ == '__main__':
    main()
