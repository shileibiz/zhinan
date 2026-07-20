#!/usr/bin/env python3
"""
Scrape major-specific admission scores for Guangdong universities from dakao100.com
and insert into the zhinan database.
"""
import re
import json
import sqlite3
import time
import urllib.request
import urllib.error
import urllib.parse
import sys
from pathlib import Path

DB_PATH = "data/zhinan.db"
DELAY = 3  # seconds between requests

# Known URLs for Guangdong universities on dakao100.com
# Format: (school_name, url)
UNIVERSITY_URLS = [
    ("中山大学", "https://www.dakao100.com/article_71909055592.html"),
    # Search for more URLs below
]

# ============================================================
# Fetch and parse a dakao100 page
# ============================================================
def fetch_page(url, retries=3):
    """Fetch HTML content from URL."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                }
            )
            resp = urllib.request.urlopen(req, timeout=30)
            content = resp.read().decode('utf-8', errors='replace')
            return content
        except Exception as e:
            print(f"  Attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt < retries - 1:
                time.sleep(2)
    return None


def parse_dakao100_table(html, school_name):
    """Parse the admission score table from a dakao100 page."""
    records = []
    
    # Find all tables
    # Pattern: look for table rows with td cells containing major, subject, score, rank
    table_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
    cell_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
    clean_tag = re.compile(r'<[^>]+>')
    
    # Also try to find the table inside article
    rows = table_pattern.findall(html)
    
    for row_html in rows:
        cells = cell_pattern.findall(row_html)
        if len(cells) >= 4:
            major = clean_tag.sub('', cells[0]).strip()
            subject = clean_tag.sub('', cells[1]).strip()
            score = clean_tag.sub('', cells[2]).strip()
            rank = clean_tag.sub('', cells[3]).strip()
            
            # Only process data rows (not header)
            if not major or major.startswith('专业') or major.startswith('科目'):
                continue
            if not score.isdigit():
                continue
            
            # Determine batch and subject type from subject field
            # e.g., "历史类(本科批)" or "物理类(本科批)"
            subject_lower = subject.lower()
            if '历史' in subject_lower or 'history' in subject_lower:
                subject_type = '历史'
            elif '物理' in subject_lower or 'physics' in subject_lower:
                subject_type = '物理'
            elif '综合' in subject_lower or '综合' in subject_lower:
                subject_type = '综合'
            else:
                subject_type = subject
            
            # Extract batch info
            batch_match = re.search(r'\((.*?)\)', subject)
            batch = batch_match.group(1) if batch_match else '本科批'
            
            # Clean major name - remove parenthetical group codes like （216）
            major_clean = re.sub(r'[（(][0-9]+[）)]', '', major).strip()
            
            records.append({
                'school': school_name,
                'major': major_clean,
                'subject_type': subject_type,
                'batch': batch,
                'score': int(score),
                'rank': int(rank) if rank.isdigit() else None,
            })
    
    return records


def find_school_id(cursor, school_name):
    """Find school ID by name, fuzzy match."""
    cursor.execute('SELECT id, name FROM schools WHERE name = ?', (school_name,))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    
    # Try fuzzy match
    cursor.execute('SELECT id, name FROM schools WHERE name LIKE ?', (f'%{school_name}%',))
    row = cursor.fetchone()
    if row:
        return row[0], row[1]
    
    print(f"  WARNING: School '{school_name}' not found in database", file=sys.stderr)
    return None, None


def find_major_id(cursor, major_name):
    """Find major ID by name."""
    cursor.execute('SELECT id, name FROM majors WHERE name = ?', (major_name,))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    # Try fuzzy
    cursor.execute('SELECT id, name FROM majors WHERE name LIKE ?', (f'%{major_name}%',))
    row = cursor.fetchone()
    if row:
        return row[0]
    
    return None


def insert_records(db_path, records, year=2024, province='广东'):
    """Insert parsed records into admission_scores table."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for rec in records:
        school_id, school_name = find_school_id(cursor, rec['school'])
        if school_id is None:
            skipped += 1
            continue
        
        major_id = find_major_id(cursor, rec['major'])
        
        # Check if record already exists
        cursor.execute(
            'SELECT id FROM admission_scores WHERE school_id=? AND year=? AND province=? AND batch=? AND min_score=? AND min_rank=?',
            (school_id, year, province, rec['batch'], rec['score'], rec['rank'])
        )
        if cursor.fetchone():
            skipped += 1
            continue
        
        cursor.execute(
            '''INSERT INTO admission_scores 
               (school_id, major_id, year, province, batch, min_score, min_rank)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (school_id, major_id, year, province, rec['batch'], rec['score'], rec['rank'])
        )
        inserted += 1
    
    conn.commit()
    conn.close()
    return inserted, skipped


# ============================================================
# Search for university pages on dakao100.com
# ============================================================
def search_dakao100(school_name):
    """Search dakao100.com for a university's Guangdong admission page."""
    search_url = f"https://www.dakao100.com/search?keyword={urllib.parse.quote(school_name + ' 广东 专业录取')}"
    try:
        req = urllib.request.Request(
            search_url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        resp = urllib.request.urlopen(req, timeout=15)
        content = resp.read().decode('utf-8', errors='replace')
        
        # Find article links
        links = re.findall(r'href=["\'](/article_\d+\.html)["\']', content)
        for link in links:
            full_url = f"https://www.dakao100.com{link}"
            print(f"  Found: {full_url}")
        return links
    except Exception as e:
        print(f"  Search failed: {e}", file=sys.stderr)
        return []


def main():
    # Schools we want data for
    target_schools = [
        "中山大学", "华南理工大学", "暨南大学", "华南师范大学",
        "广东工业大学", "深圳大学", "广东外语外贸大学", "南方医科大学",
        "华南农业大学", "广东财经大学", "广州大学", "广东医科大学",
        "广东药科大学", "广州医科大学", "广州中医药大学", "广东技术师范大学",
        "东莞理工学院", "广东海洋大学", "仲恺农业工程学院", "五邑大学",
        "惠州学院", "肇庆学院", "韶关学院", "嘉应学院",
        "韩山师范学院", "广东石油化工学院", "广州体育学院", "广州美术学院",
        "南方科技大学", "深圳技术大学", "深圳理工大学",
        "北京师范大学(珠海校区)", "哈尔滨工业大学(深圳)",
        "广东以色列理工学院", "香港中文大学(深圳)", "香港科技大学(广州)",
    ]
    
    # Manually known URLs (will expand as we find more)
    known_urls = {
        "中山大学": "https://www.dakao100.com/article_71909055592.html",
    }
    
    # Actually, let me just process what we have
    # Process 中山大学 first
    for school_name, url in known_urls.items():
        print(f"\n=== Processing {school_name} ===")
        print(f"  URL: {url}")
        
        html = fetch_page(url)
        if not html:
            print(f"  FAILED: Could not fetch page")
            continue
        
        records = parse_dakao100_table(html, school_name)
        print(f"  Parsed {len(records)} records")
        if records:
            for r in records[:3]:
                print(f"    {r['major']}: {r['subject_type']} {r['score']}分/{r['rank']}名")
            if len(records) > 3:
                print(f"    ... and {len(records)-3} more")
        
        inserted, skipped = insert_records(DB_PATH, records)
        print(f"  Inserted: {inserted}, Skipped(duplicate/not found): {skipped}")
        
        time.sleep(DELAY)


if __name__ == '__main__':
    main()
