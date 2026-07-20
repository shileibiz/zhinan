#!/usr/bin/env python3
"""
Import missing data from Gaokao-Compass-11M HuggingFace dataset.

What this imports:
1. Score-range (一分一段表) for ALL provinces (2022-2024) — was only 广东 imported before
2. Enrollment-plan (招生计划) for ALL provinces (2024) — was completely missing
3. School-admission for provinces that have data but were not imported before

Total available files: 1106 (CSV files: 861)
See assessment below for detailed coverage.
"""
import csv
import sqlite3
import time
import urllib.request
import urllib.error
import os
import sys
import re
import io
from pathlib import Path

DB_PATH = "data/zhinan.db"
BASE_URL = "https://huggingface.co/datasets/zifeiren/Gaokao-Compass-11M/resolve/main/data"

# Province name mapping
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
            resp = urllib.request.urlopen(req, timeout=120)
            content = resp.read()
            if len(content) < 100 and b'<!DOCTYPE' in content:
                print(f"    WARNING: Got HTML instead of CSV (size={len(content)})", file=sys.stderr)
                return None
            return content
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None  # File doesn't exist
            print(f"    Download attempt {attempt+1} failed: HTTP {e.code}", file=sys.stderr)
        except Exception as e:
            print(f"    Download attempt {attempt+1} failed: {e}", file=sys.stderr)
        if attempt < retries - 1:
            time.sleep(5)
    return None


def import_score_range(conn, csv_content, year, province_cn):
    """Import score-ranking table (一分一段表). Handles varying CSV formats."""
    if not csv_content or len(csv_content) < 50:
        return 0

    text = csv_content.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))

    cursor = conn.cursor()
    inserted = 0
    skipped = 0

    for row in reader:
        # Handle different column naming conventions
        score = (row.get('score') or '').strip()
        cumulative = (row.get('cumulative_count') or row.get('cumulative') or '').strip()
        category = (row.get('category') or '').strip()

        if not score:
            continue

        # Handle float scores like "695.0"
        try:
            score_val = int(float(score))
        except (ValueError, TypeError):
            continue

        if cumulative:
            try:
                rank_val = int(float(cumulative))
            except (ValueError, TypeError):
                continue
            rank_val = int(float(cumulative))
        else:
            # Some files have rank_range instead of cumulative_count
            rank_range = (row.get('rank_range') or '').strip()
            if rank_range:
                # "1-31" format — take the upper bound
                try:
                    rank_val = int(rank_range.split('-')[1])
                except (ValueError, IndexError):
                    continue
            else:
                continue

        # Determine subject type
        if category and category != '<NA>' and category != 'NA':
            subject_type = CATEGORY_MAP.get(category, category)
        else:
            # Some files have category in the filename context but not in data
            # Try to infer from batch
            batch = (row.get('batch') or '').strip()
            if '物理' in batch or '理科' in batch:
                subject_type = '物理'
            elif '历史' in batch or '文科' in batch:
                subject_type = '历史'
            else:
                subject_type = '综合'

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

        if inserted % 500 == 0:
            conn.commit()

    conn.commit()
    return inserted


def import_enrollment_plan(conn, csv_content, year, province_cn):
    """Import enrollment plan (招生计划)."""
    if not csv_content or len(csv_content) < 50:
        return 0

    text = csv_content.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))

    cursor = conn.cursor()
    inserted = 0
    skipped_no_school = 0
    skipped_dup = 0
    skipped_no_plan = 0

    # Build a school name lookup for faster matching
    cursor.execute('SELECT id, name FROM schools')
    all_schools = cursor.fetchall()
    school_by_name = {}
    school_by_fuzzy = {}
    for sid, sname in all_schools:
        school_by_name[sname] = sid
        # Also index by simplified/cleaned name
        clean = sname.replace(' ', '').replace('（', '(').replace('）', ')').replace('·', '').replace('．', '')
        school_by_fuzzy[clean] = sid

    # Build a major name lookup
    cursor.execute('SELECT id, name FROM majors')
    all_majors = cursor.fetchall()
    major_by_name = {}
    for mid, mname in all_majors:
        major_by_name[mname] = mid

    inserted_set = set()

    for row in reader:
        uni_name = (row.get('university_name') or '').strip()
        major_name = (row.get('major_name') or '').strip()
        plan_count_str = (row.get('plan_count') or '').strip()
        batch = (row.get('batch') or '').strip()
        category = (row.get('category') or '').strip()

        if not uni_name:
            skipped_no_school += 1
            continue

        # Plan count
        try:
            plan_count = int(float(plan_count_str)) if plan_count_str else None
        except (ValueError, TypeError):
            plan_count = None

        if plan_count is None or plan_count <= 0:
            skipped_no_plan += 1
            continue

        # Find school
        school_id = school_by_name.get(uni_name)
        if not school_id:
            # Try fuzzy match
            clean_uni = uni_name.replace(' ', '').replace('（', '(').replace('）', ')').replace('·', '').replace('．', '')
            school_id = school_by_fuzzy.get(clean_uni)
        if not school_id:
            # Try LIKE search (last resort)
            cursor.execute('SELECT id FROM schools WHERE name LIKE ?', (f'%{uni_name[:6]}%',))
            match = cursor.fetchone()
            if match:
                school_id = match[0]
        if not school_id:
            skipped_no_school += 1
            continue

        # Find major
        major_id = None
        if major_name:
            major_id = major_by_name.get(major_name)
            if not major_id:
                cursor.execute('SELECT id FROM majors WHERE name LIKE ?', (f'%{major_name[:8]}%',))
                match = cursor.fetchone()
                if match:
                    major_id = match[0]

        # Subject type from category
        subject_type = CATEGORY_MAP.get(category, category) if category else None

        # Build batch name
        batch_name = batch
        if subject_type and batch:
            batch_name = f"{batch}_{subject_type}"
        elif not batch:
            batch_name = f"本科批_{subject_type}" if subject_type else "本科批"

        # Check duplicate
        dedup_key = (school_id, major_id, year, province_cn, batch_name)
        if dedup_key in inserted_set:
            skipped_dup += 1
            continue

        cursor.execute(
            '''INSERT OR IGNORE INTO admission_plans 
               (school_id, major_id, year, province, batch, plan_count)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (school_id, major_id, year, province_cn, batch_name, plan_count)
        )
        if cursor.rowcount > 0:
            inserted += 1
            inserted_set.add(dedup_key)
        else:
            skipped_dup += 1

        if inserted % 2000 == 0:
            conn.commit()

    conn.commit()
    return inserted, skipped_no_school, skipped_dup, skipped_no_plan


# ================================================================
# ASSESSMENT: Which provinces have data for each category
# ================================================================

# Score-range: 29 provinces have data for 2022-2024 (missing: xizang always; hainan in 2022; qinghai in 2023-2024)
SCORE_RANGE_PROVS = [
    'anhui', 'beijing', 'chongqing', 'fujian', 'gansu', 'guangdong', 'guangxi',
    'guizhou', 'hainan', 'hebei', 'heilongjiang', 'henan', 'hubei', 'hunan',
    'jiangsu', 'jiangxi', 'jilin', 'liaoning', 'neimenggu', 'ningxia', 'qinghai',
    'shaanxi', 'shandong', 'shanghai', 'shanxi', 'sichuan', 'tianjin', 'xinjiang',
    'yunnan', 'zhejiang',
]
# But some provinces are missing for specific years (handled by 404 detection)

# Enrollment-plan: ALL 31 provinces have data for 2022-2024
ALL_PROVS = list(PROVINCE_MAP.keys())


def main():
    conn = sqlite3.connect(DB_PATH)
    total_score_range = 0
    total_enrollment = 0
    total_enrollment_skipped = 0

    # ================================================================
    # PHASE 1: Score-Range (一分一段表) — ALL provinces, 2022-2024
    # ================================================================
    print("=" * 60, flush=True)
    print("PHASE 1: Score-Range (一分一段表)", flush=True)
    print("=" * 60, flush=True)

    for year in [2022, 2023, 2024]:
        print(f"\n--- Year {year} ---", flush=True)
        for prov_en in SCORE_RANGE_PROVS:
            prov_cn = PROVINCE_MAP.get(prov_en, prov_en)
            url = f"{BASE_URL}/{year}/{prov_en}/score-range.csv?download=1"
            sys.stdout.write(f"  {prov_cn} ({year}): ")
            sys.stdout.flush()

            csv_content = download_csv(url)
            if not csv_content or len(csv_content) < 100:
                print("SKIP (empty/not found)", flush=True)
                continue

            count = import_score_range(conn, csv_content, year, prov_cn)
            print(f"{count} records", flush=True)
            total_score_range += count
            time.sleep(1.5)  # Rate limiting

    # ================================================================
    # PHASE 2: Enrollment-Plan (招生计划) — ALL provinces, 2024 first
    # ================================================================
    print("\n" + "=" * 60, flush=True)
    print("PHASE 2: Enrollment-Plan (招生计划) — 2024", flush=True)
    print("=" * 60, flush=True)

    for prov_en in ALL_PROVS:
        prov_cn = PROVINCE_MAP.get(prov_en, prov_en)
        url = f"{BASE_URL}/2024/{prov_en}/enrollment-plan.csv?download=1"
        sys.stdout.write(f"  {prov_cn} (2024): ")
        sys.stdout.flush()

        csv_content = download_csv(url)
        if not csv_content or len(csv_content) < 100:
            print("SKIP (empty/not found)", flush=True)
            continue

        inserted, skipped_school, skipped_dup, skipped_noplan = import_enrollment_plan(
            conn, csv_content, 2024, prov_cn
        )
        print(f"inserted={inserted}, "
              f"school-not-found={skipped_school}, "
              f"no-plan={skipped_noplan}, "
              f"duplicates={skipped_dup}", flush=True)
        total_enrollment += inserted
        total_enrollment_skipped += skipped_school
        time.sleep(1.5)

    # ================================================================
    # PHASE 3: School-Admission — provinces NOT in the priority list
    #           that actually have data (山东, 云南)
    # ================================================================
    print("\n" + "=" * 60, flush=True)
    print("PHASE 3: School-Admission — for provinces with data", flush=True)
    print("=" * 60, flush=True)
    # Already covered in existing script: 广东, 四川, 河南, 浙江, 安徽, 重庆, 
    #  湖南, 湖北, 江苏, 辽宁, 陕西 (these were in the priority list)
    # Provinces with actual school data not imported: 山东, 云南
    extra_school_provs = ['shandong', 'yunnan']
    for prov_en in extra_school_provs:
        prov_cn = PROVINCE_MAP.get(prov_en, prov_en)
        for year in [2024]:
            url = f"{BASE_URL}/{year}/{prov_en}/school-admission.csv?download=1"
            sys.stdout.write(f"  {prov_cn} ({year}): ")
            sys.stdout.flush()
            csv_content = download_csv(url)
            if not csv_content or len(csv_content) < 100:
                print("SKIP (empty/not found)", flush=True)
                continue

            # Use the school-admission import from existing helper
            count = import_school_admission(conn, csv_content, year, prov_en, prov_cn)
            print(f"{count} records", flush=True)
            time.sleep(1.5)

    # ================================================================
    # SUMMARY
    # ================================================================
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM rank_score_tables')
    total_rs = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM admission_plans')
    total_ap = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM admission_scores')
    total_as = cursor.fetchone()[0]

    print(f"\n{'=' * 60}", flush=True)
    print(f"IMPORT COMPLETE", flush=True)
    print(f"{'=' * 60}", flush=True)
    print(f"New score-range records:         {total_score_range}", flush=True)
    print(f"New enrollment-plan records:     {total_enrollment}", flush=True)
    print(f"  (school not found skipped: {total_enrollment_skipped})", flush=True)
    print(f"Total rank_score_tables:         {total_rs}", flush=True)
    print(f"Total admission_plans:           {total_ap}", flush=True)
    print(f"Total admission_scores:          {total_as}", flush=True)

    db_size = os.path.getsize(DB_PATH)
    print(f"DB size: {db_size / 1024 / 1024:.1f} MB", flush=True)

    conn.close()


def import_school_admission(conn, csv_content, year, province_en, province_cn):
    """Import school-level admission data (投档线) — from existing import_hf_dataset.py"""
    if not csv_content or len(csv_content) < 50:
        return 0

    text = csv_content.decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(text))

    cursor = conn.cursor()
    inserted = 0
    skipped = 0

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
            cursor.execute('SELECT id FROM schools WHERE name LIKE ?', (f'%{uni_name}%',))
            school = cursor.fetchone()
        if not school:
            skipped += 1
            continue

        school_id = school[0]
        subject_type = CATEGORY_MAP.get(category, category)
        batch_name = f"{batch}_{subject_type}" if batch else f"本科批_{subject_type}"

        try:
            min_score_val = int(float(min_score)) if min_score else None
        except (ValueError, TypeError):
            continue
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

    conn.commit()
    return inserted


if __name__ == '__main__':
    main()
