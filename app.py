"""
🏪Shop Mitra AI System - 
Powered by:  Flash OCR + Supabase Auth & Database + Random Forest ML
"""

import os
import re
import json
import warnings
import io
import urllib.parse
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image, ImageEnhance
from sklearn.ensemble import RandomForestRegressor
import gradio as gr

from google import genai
from google.genai import types
from supabase import create_client, Client

warnings.filterwarnings('ignore')

# Note: For Excel support, ensure openpyxl is installed
# pip install openpyxl

# ═══════════════════════════════════════════════════════════
# ENVIRONMENT & CLIENTS
# ═══════════════════════════════════════════════════════════

# Gemini API Setup
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your-api-key-here')
if GEMINI_API_KEY == 'your-api-key-here':
    print("⚠️ WARNING: Set GEMINI_API_KEY environment variable")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Supabase Setup
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ WARNING: Set SUPABASE_URL and SUPABASE_KEY environment variables")
    supabase: Client = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("✅ Environment loaded")

# ═══════════════════════════════════════════════════════════
# DATA STORE - SUPABASE BACKED (Multi-Tenant)
# ═══════════════════════════════════════════════════════════

class ShopDataStore:
    """Multi-tenant data store using Supabase PostgreSQL"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
    
    def add_sale(self, item, quantity, source='manual'):
        """Add a sale record to Supabase"""
        try:
            # Get current inventory item
            inv_resp = supabase.table('inventory').select('*').eq('user_id', self.user_id).eq('item_name', item).execute()
            
            if not inv_resp.data:
                return False
            
            inv_item = inv_resp.data[0]
            new_stock = max(0, inv_item['stock'] - quantity)
            
            # Update stock
            supabase.table('inventory').update({'stock': new_stock}).eq('id', inv_item['id']).execute()
            
            # Add sales history
            date = datetime.now()
            supabase.table('sales_history').insert({
                'user_id': self.user_id,
                'date': date.strftime('%Y-%m-%d'),
                'item_name': item,
                'units_sold': quantity,
                'day_of_week': date.weekday(),
                'month': date.month,
                'is_weekend': 1 if date.weekday() >= 5 else 0,
            }).execute()
            
            # Recalculate avg_daily_sale from last 30 records
            history = supabase.table('sales_history').select('units_sold').eq('user_id', self.user_id).eq('item_name', item).order('date', desc=True).limit(30).execute()
            if history.data:
                avg = round(np.mean([h['units_sold'] for h in history.data]), 1)
                supabase.table('inventory').update({'avg_daily_sale': avg}).eq('id', inv_item['id']).execute()
            
            return True
        except Exception as e:
            print(f"❌ add_sale error: {e}")
            return False
    
    def add_stock(self, item, quantity):
        """Add stock to existing item"""
        try:
            inv_resp = supabase.table('inventory').select('*').eq('user_id', self.user_id).eq('item_name', item).execute()
            if not inv_resp.data:
                return False
            
            inv_item = inv_resp.data[0]
            new_stock = inv_item['stock'] + quantity
            supabase.table('inventory').update({'stock': new_stock}).eq('id', inv_item['id']).execute()
            return True
        except Exception as e:
            print(f"❌ add_stock error: {e}")
            return False
    
    def add_new_item(self, name, stock, avg_sale, price):
        """Add a new item to inventory"""
        try:
            supabase.table('inventory').insert({
                'user_id': self.user_id,
                'item_name': name,
                'stock': int(stock),
                'avg_daily_sale': float(avg_sale),
                'price': float(price),
            }).execute()
            return True
        except Exception as e:
            print(f"❌ add_new_item error: {e}")
            return False
    
    def get_inventory_df(self):
        """Fetch inventory as pandas DataFrame"""
        try:
            resp = supabase.table('inventory').select('*').eq('user_id', self.user_id).execute()
            rows = []
            for item in resp.data:
                days = (item['stock'] / item['avg_daily_sale'] if item['avg_daily_sale'] > 0 else 999)
                if days <= 3:
                    risk = '🔴 CRITICAL'
                elif days <= 7:
                    risk = '🟠 HIGH'
                elif days <= 14:
                    risk = '🟡 MEDIUM'
                else:
                    risk = '🟢 SAFE'
                
                rows.append({
                    'Item': item['item_name'],
                    'Stock': item['stock'],
                    'Avg Daily Sale': item['avg_daily_sale'],
                    'Days Left': round(days, 1),
                    'Price (₹)': item['price'],
                    'Risk': risk,
                })
            return pd.DataFrame(rows).sort_values('Days Left') if rows else pd.DataFrame()
        except Exception as e:
            print(f"❌ get_inventory_df error: {e}")
            return pd.DataFrame()
    
    def get_inventory_dict(self):
        """Fetch inventory as dictionary for compatibility"""
        try:
            resp = supabase.table('inventory').select('*').eq('user_id', self.user_id).execute()
            inventory = {}
            for item in resp.data:
                inventory[item['item_name']] = {
                    'stock': item['stock'],
                    'avg_daily_sale': item['avg_daily_sale'],
                    'price': item['price'],
                }
            return inventory
        except Exception as e:
            print(f"❌ get_inventory_dict error: {e}")
            return {}
    
    def get_sales_history(self):
        """Fetch sales history as list of dicts"""
        try:
            resp = supabase.table('sales_history').select('*').eq('user_id', self.user_id).execute()
            return resp.data
        except Exception as e:
            print(f"❌ get_sales_history error: {e}")
            return []
    
    def has_inventory(self):
        """Check if user has any inventory"""
        try:
            resp = supabase.table('inventory').select('id').eq('user_id', self.user_id).limit(1).execute()
            return len(resp.data) > 0
        except Exception as e:
            print(f"❌ has_inventory error: {e}")
            return False


# ═══════════════════════════════════════════════════════════
# GEMINI OCR ENGINE (Multi-Tenant)
# ═══════════════════════════════════════════════════════════

class GeminiOCR:
    """Gemini 2.5 Flash OCR Engine with dynamic item fetching"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.model_name = 'gemini-2.5-flash'
    
    def _get_known_items(self):
        """Fetch user's current inventory items dynamically"""
        try:
            resp = supabase.table('inventory').select('item_name').eq('user_id', self.user_id).execute()
            return [item['item_name'] for item in resp.data]
        except:
            return []
    
    def _enhance(self, image):
        """Enhance image for better OCR"""
        if not isinstance(image, Image.Image):
            image = Image.fromarray(image)
        w, h = image.size
        if w < 400 or h < 200:
            image = image.resize((w*2, h*2), Image.LANCZOS)
        image = ImageEnhance.Contrast(image).enhance(1.8)
        image = ImageEnhance.Sharpness(image).enhance(2.0)
        return image
    
    def _match(self, extracted, known_items):
        """Match extracted text to known items"""
        if not extracted:
            return 'Unknown'
        ext = extracted.lower()
        
        # Exact match
        for k in known_items:
            if k.lower() == ext:
                return k
        
        # Partial match
        for k in known_items:
            if k.lower() in ext or ext in k.lower():
                return k
        
        # Keyword fallback
        kw = {
            'pencil': 'Pencil', 'pen': 'Pen Blue', 'eraser': 'Eraser',
            'rubber': 'Eraser', 'sharp': 'Sharpener', 'notebook': 'Notebook A4',
            'copy': 'Notebook A5', 'ruler': 'Ruler', 'scale': 'Ruler',
            'stapl': 'Stapler', 'geomet': 'Geometry Box', 'colour': 'Colour Pencils',
            'color': 'Colour Pencils', 'marker': 'Marker', 'highlight': 'Highlighter',
            'glue': 'Glue Stick', 'scissor': 'Scissors', 'calculat': 'Calculator',
            'folder': 'File Folder', 'sticky': 'Sticky Notes', 'drawing': 'Drawing Book',
        }
        for k, v in kw.items():
            if k in ext:
                return v
        
        return extracted.title()
    
    def _parse_response(self, raw_text):
        """Parse Gemini JSON response"""
        try:
            text = raw_text.strip()
            if text.startswith('```json'):
                text = text[7:]
            elif text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
            
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if m:
                return json.loads(m.group())
            return json.loads(text)
        except Exception as e:
            print(f"JSON Parse Error: {e}")
            return None
    
    def from_image(self, image):
        """Extract items from image using Gemini Vision"""
        if image is None:
            return ("❌ Image upload karo!", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))
        
        try:
            known_items = self._get_known_items()
            enhanced = self._enhance(image)
            
            prompt = f"""
You are an expert OCR system for an IndianShop Mitra.
Read ALL text from the image carefully — including handwritten text.
Known items in shop: {', '.join(known_items)}
Rules:
1. Read every word carefully, even if handwritten or unclear
2. Map brand + item to item type only:
   • Apsara/Natraj Pencil  → item: Pencil,    brand: Apsara/Natraj
   • Cello/Reynolds Pen    → item: Pen Blue,  brand: Cello/Reynolds
3. Parse quantity units correctly: "1 BOX" → unit:box | "5 pcs" → unit:pcs
4. Default quantity = 1 if not written

Return ONLY this JSON:
{{
  "raw_text": "<exact text seen in image>",
  "image_type": "bill/invoice",
  "items": [
    {{
      "item": "<matched known item>",
      "quantity": 1,
      "unit": "pcs",
      "brand": "<brand>",
      "confidence": "high",
      "original_text": "<text>"
    }}
  ]
}}"""
            
            resp = gemini_client.models.generate_content(
                model=self.model_name,
                contents=[prompt, enhanced],
                config=types.GenerateContentConfig(temperature=0.1)
            )
            
            data = self._parse_response(resp.text.strip())
            if data is None:
                return (f"⚠️ Parse error:\n{resp.text[:400]}", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))
            
            items = data.get('items', [])
            raw = data.get('raw_text', 'N/A')
            itype = data.get('image_type', 'unknown')
            
            if not items:
                return (f"⚠️ Koi item nahi mila.\nImage type : {itype}\nRaw text : {raw}", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))
            
            status = f"✅ {len(items)} items mile!\n{'─'*40}\n🖼️ Type : {itype}\n📝 Text : {raw}\n{'─'*40}\n✏️ Neeche table edit karo"
            
            rows = []
            for i in items:
                rows.append({
                    'Item': self._match(i.get('item', ''), known_items),
                    'Quantity': int(i.get('quantity', 1)),
                    'Unit': i.get('unit', 'pcs'),
                    'Brand': i.get('brand', '-'),
                    'Confidence': i.get('confidence', 'medium'),
                    'Original Text': i.get('original_text', '-')
                })
            
            return status, pd.DataFrame(rows)
        
        except Exception as e:
            return (f"❌ Error: {e}", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))
    
    def from_text(self, text):
        """Extract items from text using Gemini"""
        if not text.strip():
            return ("❌ Text daalo!", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))
        
        try:
            known_items = self._get_known_items()
            prompt = f"""
Extract stationary items from this text for an Indian shop.
Text: "{text}"
Known items: {', '.join(known_items)}
Return ONLY JSON:
{{ "items": [ {{"item": "<item>", "quantity": 1, "unit": "pcs", "brand": "<brand>", "confidence": "high"}} ] }}"""
            
            resp = gemini_client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            
            data = self._parse_response(resp.text.strip())
            if data is None:
                return ("⚠️ Parse error!", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))
            
            items = data.get('items', [])
            rows = []
            for i in items:
                rows.append({
                    'Item': self._match(i.get('item', ''), known_items),
                    'Quantity': int(i.get('quantity', 1)),
                    'Unit': i.get('unit', 'pcs'),
                    'Brand': i.get('brand', '-'),
                    'Confidence': i.get('confidence', 'medium'),
                    'Original Text': text[:60]
                })
            
            return f"✅ {len(rows)} items mile!", pd.DataFrame(rows)
        
        except Exception as e:
            return (f"❌ Error: {e}", pd.DataFrame(columns=['Item','Quantity','Unit','Brand','Confidence','Original Text']))


# ═══════════════════════════════════════════════════════════
# PREDICTION ENGINE (Multi-Tenant)
# ═══════════════════════════════════════════════════════════

class PredictionEngine:
    """Random Forest prediction engine with Supabase data"""
    
    def __init__(self, data_store: ShopDataStore):
        self.store = data_store
        self.models = {}
    
    def train(self):
        """Train Random Forest models for each item"""
        history = self.store.get_sales_history()
        if not history:
            return
        
        df = pd.DataFrame(history)
        inventory = self.store.get_inventory_dict()
        
        for item in inventory.keys():
            idf = df[df['item_name'] == item].reset_index(drop=True)
            if len(idf) < 5:
                continue
            
            idf['day_num'] = range(len(idf))
            X = idf[['day_num', 'day_of_week', 'month', 'is_weekend']]
            y = idf['units_sold']
            
            try:
                m = RandomForestRegressor(n_estimators=30, random_state=42)
                m.fit(X, y)
                self.models[item] = {'model': m, 'last_day': len(idf)}
            except:
                pass
    
    def predict_item(self, item_name, days=30):
        """Predict future sales and stockout date for an item"""
        inventory = self.store.get_inventory_dict()
        if item_name not in inventory:
            return None, []
        
        props = inventory[item_name]
        remaining = props['stock']
        today = datetime.now()
        preds, stockout = [], None
        info = self.models.get(item_name)
        
        for i in range(1, days + 1):
            future = today + timedelta(days=i)
            if info:
                feat = pd.DataFrame({
                    'day_num': [info['last_day'] + i],
                    'day_of_week': [future.weekday()],
                    'month': [future.month],
                    'is_weekend': [1 if future.weekday() >= 5 else 0],
                })
                try:
                    sale = max(0, int(info['model'].predict(feat)[0]))
                except:
                    sale = int(props['avg_daily_sale'] * max(0.2, np.random.normal(1, 0.2)))
            else:
                sale = int(props['avg_daily_sale'] * max(0.2, np.random.normal(1, 0.2)))
            
            remaining -= sale
            preds.append({
                'day': i,
                'date': future.strftime('%d %b'),
                'sale': max(0, sale),
                'remaining': max(0, remaining)
            })
            if remaining <= 0 and stockout is None:
                stockout = future
        
        return stockout, preds
    
    def all_predictions(self):
        """Generate predictions for all items"""
        self.train()
        results = []
        inventory = self.store.get_inventory_dict()
        
        for item, props in inventory.items():
            stockout, preds = self.predict_item(item)
            days_left = (props['stock'] / props['avg_daily_sale'] if props['avg_daily_sale'] > 0 else 999)
            
            if days_left <= 3:
                risk = '🔴 CRITICAL'
            elif days_left <= 7:
                risk = '🟠 HIGH'
            elif days_left <= 14:
                risk = '🟡 MEDIUM'
            else:
                risk = '🟢 SAFE'
            
            results.append({
                'item': item,
                'stock': props['stock'],
                'avg_sale': round(props['avg_daily_sale'], 1),
                'days_left': round(days_left, 1),
                'stockout': (stockout.strftime('%d %b %Y') if stockout else '>30 days'),
                'risk': risk,
                'order_qty': int(props['avg_daily_sale'] * 30),
                'preds': preds,
            })
        
        return sorted(results, key=lambda x: x['days_left'])


# ═══════════════════════════════════════════════════════════
# CHART HELPERS
# ═══════════════════════════════════════════════════════════

CLR = {'🔴 CRITICAL': '#ff4757', '🟠 HIGH': '#ff6b35', '🟡 MEDIUM': '#ffd32a', '🟢 SAFE': '#2ed573'}

def _buf_to_pil(fig):
    """Convert matplotlib figure to PIL Image"""
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor='#0f0f23')
    buf.seek(0)
    plt.close(fig)
    image = Image.open(buf).copy()
    buf.close()
    return image

def _style_ax(ax):
    """Style matplotlib axis with dark theme"""
    ax.set_facecolor('#1a1a3e')
    [sp.set_visible(False) for sp in ax.spines.values()]
    ax.tick_params(colors='white', labelsize=8)
    ax.grid(color='#2a2a4a', alpha=0.5)

def make_message_chart(title, message):
    """Render a simple message as a chart image so Gradio never shows a blank image."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 4))
    fig.patch.set_facecolor('#0f0f23')
    ax.set_facecolor('#1a1a3e')
    ax.text(0.5, 0.58, title, ha='center', va='center', color='white', fontsize=16, fontweight='bold')
    ax.text(0.5, 0.42, message, ha='center', va='center', color='#d7dbff', fontsize=11, wrap=True)
    ax.axis('off')
    return _buf_to_pil(fig)

def make_dashboard(results, store):
    """Generate 4-panel dashboard image"""
    if not results:
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
        fig.patch.set_facecolor('#0f0f23')
        ax.text(0.5, 0.5, 'No data available', ha='center', va='center', color='white', fontsize=16)
        ax.axis('off')
        return _buf_to_pil(fig)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.patch.set_facecolor('#0f0f23')
    
    # Chart 1: Days Left Bar Chart
    ax = axes[0, 0]
    _style_ax(ax)
    items = [r['item'] for r in results[:15]]
    days = [min(r['days_left'], 35) for r in results[:15]]
    cols = [CLR.get(r['risk'], '#aaa') for r in results[:15]]
    bars = ax.barh(items, days, color=cols, edgecolor='#2a2a4a', height=0.7)
    ax.axvline(7, color='#ff4757', ls='--', lw=1.5, alpha=.8, label='7d')
    ax.axvline(14, color='#ffd32a', ls='--', lw=1.5, alpha=.8, label='14d')
    ax.set_title('📅 Stock Kitne Din Ka?', color='white', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8, labelcolor='white', facecolor='#2a2a4a')
    for b, v in zip(bars, days):
        ax.text(b.get_width() + .3, b.get_y() + b.get_height() / 2, f'{v:.0f}d', va='center', color='white', fontsize=7)
    
    # Chart 2: Risk Distribution Pie
    ax = axes[0, 1]
    ax.set_facecolor('#1a1a3e')
    rc = {}
    for r in results:
        k = r['risk'].split(' ', 1)[1]
        rc[k] = rc.get(k, 0) + 1
    if rc:
        labels = list(rc.keys())
        pcols = ['#ff4757' if 'CRIT' in l else '#ff6b35' if 'HIGH' in l else '#ffd32a' if 'MED' in l else '#2ed573' for l in labels]
        _, _, autos = ax.pie(list(rc.values()), labels=labels, colors=pcols, autopct='%1.0f%%', startangle=90, 
                            textprops={'color': 'white', 'fontsize': 9}, wedgeprops={'edgecolor': '#0f0f23', 'linewidth': 2})
        [a.set_color('white') for a in autos]
    ax.set_title('⚡ Risk Distribution', color='white', fontsize=11, fontweight='bold')
    
    # Chart 3: Top Sellers
    ax = axes[1, 0]
    _style_ax(ax)
    top = sorted(results, key=lambda x: x['avg_sale'], reverse=True)[:10]
    ax.bar(range(len(top)), [r['avg_sale'] for r in top], color='#5352ed', edgecolor='#2a2a4a')
    ax.set_xticks(range(len(top)))
    ax.set_xticklabels([r['item'] for r in top], rotation=45, ha='right', color='white', fontsize=7)
    ax.set_title('🏆 Top Sellers', color='white', fontsize=11, fontweight='bold')
    
    # Chart 4: Stock vs Suggested Order Quantity
    ax = axes[1, 1]
    _style_ax(ax)
    ri = ([r for r in results if '🔴' in r['risk'] or '🟠' in r['risk']][:8] or results[:8])
    x = np.arange(len(ri))
    ax.bar(x - .18, [r['stock'] for r in ri], .35, label='Current Stock', color='#5352ed', alpha=.85)
    ax.bar(x + .18, [r['order_qty'] for r in ri], .35, label='Suggested Order', color='#ff6b35', alpha=.85)
    ax.set_xticks(x)
    ax.set_xticklabels([r['item'] for r in ri], rotation=45, ha='right', color='white', fontsize=7)
    ax.set_title('⚖️ Stock vs Suggested Order', color='white', fontsize=11, fontweight='bold')
    ax.legend(fontsize=8, labelcolor='white', facecolor='#2a2a4a')
    
    plt.tight_layout()
    return _buf_to_pil(fig)

def make_future_stock_projection_bar_chart(item_name, preds):
    """Generate a future stock projection bar chart from forecast data."""
    if not preds:
        fig, ax = plt.subplots(1, 1, figsize=(10, 5))
        fig.patch.set_facecolor('#0f0f23')
        ax.text(0.5, 0.5, 'No prediction data', ha='center', va='center', color='white', fontsize=14)
        ax.axis('off')
        return _buf_to_pil(fig)
    
    fig, ax = plt.subplots(1, 1, figsize=(13, 5.5))
    fig.patch.set_facecolor('#0f0f23')
    _style_ax(ax)
    
    days = [p['day'] for p in preds]
    labels = [p['date'] for p in preds]
    remaining = [p['remaining'] for p in preds]
    projected_sales = [p['sale'] for p in preds]
    starting_stock = remaining[0] + projected_sales[0]
    reorder_threshold = max(1, int(np.ceil(np.mean(projected_sales) * 7))) if projected_sales else 1
    stockout_days = [p['day'] for p in preds if p['remaining'] <= 0]
    stockout_day = stockout_days[0] if stockout_days else None
    
    colors = [
        '#ff4757' if qty <= 0 else
        '#ff6b35' if qty <= reorder_threshold else
        '#2ed573'
        for qty in remaining
    ]

    bars = ax.bar(days, remaining, color=colors, edgecolor='#2a2a4a', width=0.72)
    ax.axhline(
        reorder_threshold,
        color='#ffd32a',
        linestyle='--',
        linewidth=1.6,
        alpha=0.9,
        label=f'Reorder threshold ({reorder_threshold} units)'
    )

    if stockout_day:
        ax.axvline(stockout_day, color='#ff4757', linestyle=':', linewidth=2, alpha=0.9, label=f'Stockout day {stockout_day}')
    
    ax.set_xlabel('Days Ahead', color='white', fontsize=10)
    ax.set_ylabel('Projected Stock Remaining', color='white', fontsize=10)
    ax.set_title(f'📈 30-Day Forecast: {item_name}', color='white', fontsize=12, fontweight='bold')
    ax.set_title(f'Future Stock Projection: {item_name}', color='white', fontsize=12, fontweight='bold')
    
    ax.tick_params(axis='y', labelcolor='white')
    
    ax.set_ylim(0, max(starting_stock, reorder_threshold, max(remaining, default=0)) * 1.18 + 1)
    ax.set_xticks(days[::2])
    ax.set_xticklabels(labels[::2], rotation=45, ha='right', color='white', fontsize=8)

    labeled_days = set(days[::5])
    if stockout_day:
        labeled_days.add(stockout_day)
    for bar, day, qty in zip(bars, days, remaining):
        if day in labeled_days or qty <= 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                max(qty, 0) + 0.4,
                str(int(qty)),
                ha='center',
                va='bottom',
                color='white',
                fontsize=7
            )

    ax.legend(fontsize=9, labelcolor='white', facecolor='#2a2a4a', loc='upper right')
    
    plt.tight_layout()
    return _buf_to_pil(fig)


# ═══════════════════════════════════════════════════════════
# AUTHENTICATION HANDLERS
# ═══════════════════════════════════════════════════════════

def handle_signup(email, password):
    """Sign up new user with Supabase Auth"""
    try:
        if not email or not password:
            return "❌ Email and password required!", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
        
        if len(password) < 6:
            return "❌ Password must be at least 6 characters!", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
        
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        if response.user:
            # Auto login after signup
            login_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if login_response.user:
                user_id = login_response.user.id
                return f"✅ Account created! Welcome {email}", user_id, gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
        
        return "❌ Signup failed. Email may already exist.", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
    
    except Exception as e:
        return f"❌ Error: {str(e)}", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)

def handle_login(email, password):
    """Login existing user with Supabase Auth"""
    try:
        if not email or not password:
            return "❌ Email and password required!", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
        
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        if response.user:
            user_id = response.user.id
            return f"✅ Welcome back {email}!", user_id, gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
        
        return "❌ Invalid credentials!", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
    
    except Exception as e:
        return f"❌ Error: {str(e)}", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)

def handle_logout():
    """Logout user"""
    try:
        supabase.auth.sign_out()
    except:
        pass
    return "👋 Logged out", None, gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)

def check_onboarding_status(user_id):
    """Check if user has completed onboarding (has inventory)"""
    if not user_id:
        return gr.update(visible=True), gr.update(visible=False), gr.update(visible=False)
    
    store = ShopDataStore(user_id)
    has_inv = store.has_inventory()
    
    if has_inv:
        return gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)
    else:
        return gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)


# ═══════════════════════════════════════════════════════════
# ONBOARDING HANDLERS
# ═══════════════════════════════════════════════════════════

def handle_add_onboarding_item(user_id, name, stock, avg_sale, price):
    """Add item during onboarding"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    try:
        store = ShopDataStore(user_id)
        if not name or stock is None or avg_sale is None or price is None:
            return "❌ All fields required!", store.get_inventory_df()
        
        store.add_new_item(name, stock, avg_sale, price)
        return f"✅ {name} added!", store.get_inventory_df()
    except Exception as e:
        return f"❌ Error: {e}", pd.DataFrame()

def handle_finish_onboarding(user_id):
    """Complete onboarding and go to main dashboard"""
    if not user_id:
        return "❌ Not logged in!", gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
    
    store = ShopDataStore(user_id)
    if not store.has_inventory():
        return "❌ Add at least 1 item first!", gr.update(visible=False), gr.update(visible=True), gr.update(visible=False)
    
    return "✅ Setup complete! Welcome to your dashboard", gr.update(visible=False), gr.update(visible=False), gr.update(visible=True)


# ═══════════════════════════════════════════════════════════
# MAIN DASHBOARD HANDLERS
# ═══════════════════════════════════════════════════════════

def handle_ocr_scan(user_id, image, text_input, source):
    """Handle OCR scan from image or text"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    ocr = GeminiOCR(user_id)
    
    if source == "📸 Image" and image is not None:
        status, df = ocr.from_image(image)
        return status, df
    elif source == "✍️ Text" and text_input:
        status, df = ocr.from_text(text_input)
        return status, df
    else:
        return "❌ Please provide input!", pd.DataFrame()

def confirm_sales(user_id, df, ocr_mode):
    """Confirm and record sales/purchases from OCR table"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    try:
        store = ShopDataStore(user_id)
        
        # Handle Gradio DataFrame format
        if isinstance(df, dict):
            if 'data' in df:
                rows = df['data']
            else:
                rows = []
        else:
            rows = df.to_dict('records') if hasattr(df, 'to_dict') else []
        
        if not rows:
            return "❌ No items to confirm!", store.get_inventory_df()
        
        # Determine if this is a sale (subtract) or purchase (add)
        is_sale = "Sale" in ocr_mode or "Minus" in ocr_mode
        
        success_count = 0
        for row in rows:
            item = row.get('Item', '')
            qty = row.get('Quantity', 0)
            if item and qty > 0:
                if is_sale:
                    # Sale: subtract from stock
                    if store.add_sale(item, qty, source='ocr'):
                        success_count += 1
                else:
                    # Purchase: add to stock
                    if store.add_stock(item, qty):
                        success_count += 1
        
        action_type = "sales" if is_sale else "purchases"
        return f"✅ {success_count} {action_type} recorded!", store.get_inventory_df()
    
    except Exception as e:
        return f"❌ Error: {e}", pd.DataFrame()

def handle_manual_sale(user_id, item, qty):
    """Record manual sale"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    try:
        store = ShopDataStore(user_id)
        if not item or qty <= 0:
            return "❌ Invalid input!", store.get_inventory_df()
        
        if store.add_sale(item, qty):
            return f"✅ Sold {qty}x {item}", store.get_inventory_df()
        else:
            return f"❌ Item {item} not found!", store.get_inventory_df()
    except Exception as e:
        return f"❌ Error: {e}", pd.DataFrame()

def handle_add_stock(user_id, item, qty):
    """Add stock to existing item"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    try:
        store = ShopDataStore(user_id)
        if not item or qty <= 0:
            return "❌ Invalid input!", store.get_inventory_df()
        
        if store.add_stock(item, qty):
            return f"✅ Added {qty}x {item} to stock", store.get_inventory_df()
        else:
            return f"❌ Item {item} not found!", store.get_inventory_df()
    except Exception as e:
        return f"❌ Error: {e}", pd.DataFrame()

def handle_add_new_item(user_id, name, stock, avg_sale, price):
    """Add completely new item to inventory"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    try:
        store = ShopDataStore(user_id)
        if not name or stock is None or avg_sale is None or price is None:
            return "❌ All fields required!", store.get_inventory_df()
        
        if store.add_new_item(name, stock, avg_sale, price):
            return f"✅ {name} added to inventory!", store.get_inventory_df()
        else:
            return "❌ Failed to add item!", store.get_inventory_df()
    except Exception as e:
        return f"❌ Error: {e}", pd.DataFrame()

def handle_excel_upload(user_id, file_obj):
    """Handle bulk Excel/CSV upload for inventory items"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame()
    
    if file_obj is None:
        return "❌ Please upload a file!", pd.DataFrame()
    
    try:
        store = ShopDataStore(user_id)
        
        # Safely extract file path from Gradio file object
        file_path = str(file_obj.name if hasattr(file_obj, 'name') else file_obj)
        
        # Check file extension and read accordingly
        file_lower = file_path.lower()
        df = None
        
        if file_lower.endswith('.csv'):
            # CSV file - read with pandas
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                return f"❌ CSV file read error: {str(e)}", store.get_inventory_df()
        
        elif file_lower.endswith('.xlsx') or file_lower.endswith('.xls'):
            # Excel file - read with openpyxl engine
            try:
                df = pd.read_excel(file_path, engine='openpyxl')
            except ImportError:
                return "❌ openpyxl library missing!\n\nPlease install it:\n• Local: pip install openpyxl\n• Colab: !pip install openpyxl\n\nThen restart the app.", store.get_inventory_df()
            except Exception as e:
                return f"❌ Excel file read error: {str(e)}\n\nMake sure the file is a valid Excel file.", store.get_inventory_df()
        
        else:
            # Unsupported file type
            return "❌ Unsupported file format!\n\nPlease upload:\n• CSV files (.csv)\n• Excel files (.xlsx or .xls)", store.get_inventory_df()
        
        # Strip whitespace from column names for robust validation
        df.columns = df.columns.str.strip()
        
        # Check for required columns (exact match, case-sensitive)
        required_columns = ['Item Name', 'Stock', 'Avg Daily Sale', 'Price']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return f"❌ Missing required columns: {', '.join(missing_columns)}\nRequired: {', '.join(required_columns)}", store.get_inventory_df()
        
        # Validate and add items
        added_count = 0
        errors = []
        
        for idx, row in df.iterrows():
            try:
                # Safely extract item name
                item_name = str(row.get('Item Name', '')).strip()
                
                # Skip empty rows
                if not item_name or item_name.lower() == 'nan':
                    continue
                
                # Safely cast numeric values with defaults
                try:
                    stock = int(float(row.get('Stock', 0)))
                except (ValueError, TypeError):
                    errors.append(f"Row {idx+2}: {item_name} - Invalid Stock value")
                    continue
                
                try:
                    avg_sale = float(row.get('Avg Daily Sale', 1.0))
                except (ValueError, TypeError):
                    errors.append(f"Row {idx+2}: {item_name} - Invalid Avg Daily Sale value")
                    continue
                
                try:
                    price = float(row.get('Price', 0.0))
                except (ValueError, TypeError):
                    errors.append(f"Row {idx+2}: {item_name} - Invalid Price value")
                    continue
                
                # Validate values are positive
                if stock < 0 or avg_sale < 0 or price < 0:
                    errors.append(f"Row {idx+2}: {item_name} - Negative values not allowed")
                    continue
                
                # Add item to database
                if store.add_new_item(item_name, stock, avg_sale, price):
                    added_count += 1
                else:
                    errors.append(f"Row {idx+2}: {item_name} - Failed to add (may already exist)")
                
            except Exception as e:
                errors.append(f"Row {idx+2}: {str(e)}")
        
        # Build status message
        if added_count == 0 and not errors:
            status_msg = "⚠️ No items found in file or all rows were empty"
        elif added_count > 0:
            status_msg = f"✅ Successfully added {added_count} items!"
        else:
            status_msg = "❌ No items could be added"
        
        if errors:
            status_msg += f"\n\n⚠️ {len(errors)} errors encountered:\n"
            # Show first 5 errors
            for error in errors[:5]:
                status_msg += f"  • {error}\n"
            if len(errors) > 5:
                status_msg += f"  • ... and {len(errors) - 5} more errors"
        
        return status_msg, store.get_inventory_df()
    
    except pd.errors.EmptyDataError:
        return "❌ The file is empty!", store.get_inventory_df()
    except Exception as e:
        error_msg = str(e).lower()
        
        # Check for openpyxl missing error
        if "openpyxl" in error_msg or "no module named 'openpyxl'" in error_msg:
            return "❌ openpyxl library missing!\n\nPlease install it:\n• Local: pip install openpyxl\n• Colab: !pip install openpyxl\n\nThen restart the app.", pd.DataFrame()
        
        return f"❌ Error reading file: {str(e)}", pd.DataFrame()

def refresh_inventory(user_id):
    """Refresh inventory display"""
    if not user_id:
        return pd.DataFrame()
    
    store = ShopDataStore(user_id)
    return store.get_inventory_df()

def run_predictions(user_id):
    """Generate predictions and dashboard with action plan"""
    if not user_id:
        return "❌ Not logged in!", pd.DataFrame(), None, ""
    
    try:
        store = ShopDataStore(user_id)
        engine = PredictionEngine(store)
        results = engine.all_predictions()
        
        if not results:
            return "⚠️ No predictions available!", pd.DataFrame(), None, ""
        
        # Create prediction table
        pred_df = pd.DataFrame([{
            'Item': r['item'],
            'Stock': r['stock'],
            'Avg Sale': r['avg_sale'],
            'Days Left': r['days_left'],
            'Stockout Date': r['stockout'],
            'Risk': r['risk'],
            'Suggested Order': r['order_qty']
        } for r in results])
        
        # Generate dashboard image
        dashboard_img = make_dashboard(results, store)
        
        # Generate action plan text
        action_plan = "📋 *INVENTORY ACTION PLAN*\n\n"
        
        # Critical items (need immediate attention)
        critical_items = [r for r in results if '🔴' in r['risk'] or r['days_left'] <= 3 or r['stock'] < (r['avg_sale'] * 3)]
        if critical_items:
            action_plan += "⚠️ *URGENT - Order Immediately:*\n"
            for item in critical_items:
                action_plan += f"  • {item['item']}: {item['order_qty']} units (Stock: {item['stock']}, {item['days_left']:.1f} days left)\n"
            action_plan += "\n"
        
        # High priority items
        high_items = [r for r in results if '🟠' in r['risk'] and r not in critical_items]
        if high_items:
            action_plan += "🟠 *HIGH PRIORITY - Order Soon:*\n"
            for item in high_items:
                action_plan += f"  • {item['item']}: {item['order_qty']} units (Stock: {item['stock']}, {item['days_left']:.1f} days left)\n"
            action_plan += "\n"
        
        # Medium priority items
        medium_items = [r for r in results if '🟡' in r['risk']]
        if medium_items:
            action_plan += "🟡 *MEDIUM PRIORITY - Monitor:*\n"
            for item in medium_items[:5]:  # Show top 5
                action_plan += f"  • {item['item']}: {item['order_qty']} units (Stock: {item['stock']}, {item['days_left']:.1f} days left)\n"
            if len(medium_items) > 5:
                action_plan += f"  ... and {len(medium_items) - 5} more items\n"
        
        return f"✅ Predictions generated for {len(results)} items!", pred_df, dashboard_img, action_plan
    
    except Exception as e:
        return f"❌ Error: {e}", pd.DataFrame(), None, ""

def show_future_stock_projection(user_id, item_name):
    """Show 30-day future stock projection for a specific item."""
    if not user_id:
        return make_message_chart('Login required', 'Please login before generating a stock projection.')
    if not item_name or not item_name.strip():
        return make_message_chart('Item required', 'Type an item name from your inventory.')
    
    try:
        store = ShopDataStore(user_id)
        inventory = store.get_inventory_dict()
        item_lookup = {name.strip().lower(): name for name in inventory.keys()}
        matched_item = item_lookup.get(item_name.strip().lower())

        if not matched_item:
            available = ', '.join(list(inventory.keys())[:8]) or 'No inventory items found'
            return make_message_chart('Item not found', f'No inventory item matched "{item_name}". Available: {available}')

        engine = PredictionEngine(store)
        engine.train()
        stockout, preds = engine.predict_item(matched_item)
        
        if not preds:
            return make_message_chart('No projection data', f'Could not generate projection for {matched_item}.')
        
        return make_future_stock_projection_bar_chart(matched_item, preds)
    
    except Exception as e:
        print(f"❌ Trend error: {e}")
        return make_message_chart('Projection error', str(e))

def generate_wa_order_link(user_id, plan_text, phone_number):
    """Generate WhatsApp order link from action plan"""
    if not user_id:
        return "❌ Please login first"
    
    if not plan_text or not plan_text.strip():
        return "❌ No action plan generated yet. Click 'Generate Predictions' first."
    
    if not phone_number or not phone_number.strip():
        return "❌ Please enter vendor's phone number (with country code, e.g., 919876543210)"
    
    try:
        # Clean phone number (remove spaces, dashes, etc.)
        clean_phone = ''.join(filter(str.isdigit, phone_number))
        
        # Validate phone number
        if len(clean_phone) < 10:
            return "❌ Invalid phone number. Please enter a valid number with country code."
        
        # Format message
        message = f"🛒 *Inventory Order Request*\n\n{plan_text}\n\n---\nGenerated byShop Mitra AI System"
        
        # URL encode the message
        encoded_message = urllib.parse.quote(message)
        
        # Create WhatsApp link
        wa_link = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_message}"
        
        # Return HTML button
        html_button = f'''
        <div style="margin-top: 10px;">
            <a href="{wa_link}" target="_blank" style="
                display: inline-block;
                background-color: #25D366;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 8px;
                font-weight: bold;
                font-size: 16px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.2);
            ">
                📱 Send Order via WhatsApp
            </a>
            <p style="color: #888; font-size: 12px; margin-top: 8px;">
                Click the button to open WhatsApp with your order message
            </p>
        </div>
        '''
        
        return html_button
    
    except Exception as e:
        return f"❌ Error generating link: {str(e)}"


# ═══════════════════════════════════════════════════════════
# GRADIO UI - MULTI-PAGE LAYOUT
# ═══════════════════════════════════════════════════════════

css = """
* { font-family:'Segoe UI',Arial,sans-serif !important; }
.gradio-container { background:linear-gradient(135deg,#0f0f23 0%,#1a1a3e 100%) !important; }
.main-header { background:linear-gradient(135deg,#667eea,#764ba2); padding:20px; border-radius:15px; text-align:center; margin-bottom:16px; box-shadow:0 8px 32px rgba(102,126,234,.3); }
.sec { color:#a0a0ff; font-size:14px; font-weight:bold; margin:10px 0 6px; padding:8px 12px; background:#1a1a3e; border-left:3px solid #667eea; border-radius:0 8px 8px 0; }
.btn { font-size:14px !important; font-weight:600 !important; border-radius:8px !important; }
.dataframe { border-radius:8px; overflow:hidden; }
"""

with gr.Blocks(css=css, title="🏪Shop Mitra AI - Multi-Tenant SaaS") as app:
    
    # Session State
    user_session = gr.State(value=None)  # Stores user_id when logged in
    
    gr.HTML("""
    <div class="main-header">
        <h1 style="margin:0;color:white;font-size:28px;">🏪Shop Mitra AI System</h1>
        <p style="margin:8px 0 0;color:#e0e0ff;font-size:14px;">   OCR +  ML Predictions</p>
    </div>
    """)
    
    # ═══════════════════════════════════════════════════════════
    # PAGE 1: AUTH PAGE
    # ═══════════════════════════════════════════════════════════
    
    with gr.Column(visible=True) as auth_page:
        gr.Markdown("## 🔐 Login or Sign Up")
        
        with gr.Tab("Login"):
            login_email = gr.Textbox(label="Email", placeholder="you@example.com")
            login_password = gr.Textbox(label="Password", type="password")
            login_btn = gr.Button("🔑 Login", variant="primary")
            login_status = gr.Textbox(label="Status", interactive=False)
        
        with gr.Tab("Sign Up"):
            signup_email = gr.Textbox(label="Email", placeholder="you@example.com")
            signup_password = gr.Textbox(label="Password", type="password")
            gr.Markdown("*Password must be at least 6 characters*")
            signup_btn = gr.Button("📝 Create Account", variant="primary")
            signup_status = gr.Textbox(label="Status", interactive=False)
    
    # ═══════════════════════════════════════════════════════════
    # PAGE 2: ONBOARDING PAGE
    # ═══════════════════════════════════════════════════════════
    
    with gr.Column(visible=False) as onboarding_page:
        gr.Markdown("""
## 🎉 Welcome! Let's Setup Your Shop

### How to Use This App:
1. **Add Your Inventory**: Start by adding your stationery items below
2. **Scan Bills**: Use OCR to automatically extract sales from bill images
3. **Track Stock**: Monitor your inventory in real-time
4. **Get Predictions**: ML-powered forecasts tell you when to reorder

### Quick Start: Add Your First Items
Choose how you'd like to add items - bulk upload or manual entry.
        """)
        
        # Tabbed interface for different input methods
        with gr.Tabs():
            # Tab 1: Bulk Excel Upload
            with gr.Tab("📄 Bulk Excel Upload"):
                gr.Markdown("""
### 📋 Upload Your Inventory from Excel/CSV

Upload a spreadsheet file to add multiple items at once. Your file must contain these exact columns:

| Column Name | Description | Example |
|-------------|-------------|---------|
| **Item Name** | Name of the item | Pencil, Pen Blue, Eraser |
| **Stock** | Current stock quantity | 50, 100, 25 |
| **Avg Daily Sale** | Average units sold per day | 5, 10, 3 |
| **Price** | Price in rupees (₹) | 5, 10, 3 |

**Format Requirements:**
- File format: `.csv` or `.xlsx`
- Column names must match exactly (case-sensitive)
- All values must be positive numbers

**Sample Template:** See `inventory_template.csv` in project folder
                """)
                
                onboard_excel_file = gr.File(
                    label="Upload Excel/CSV File",
                    file_types=[".csv", ".xlsx", ".xls"],
                    type="filepath"
                )
                onboard_excel_btn = gr.Button("📤 Upload & Import Items", variant="primary", size="lg")
            
            # Tab 2: Manual Entry
            with gr.Tab("✍️ Add Manually"):
                gr.Markdown("### ➕ Add Inventory Items One by One")
                gr.Markdown("Fill in the details below to add items to your inventory manually.")
                
                with gr.Row():
                    onboard_name = gr.Textbox(label="Item Name", placeholder="Pencil")
                    onboard_stock = gr.Number(label="Current Stock", value=50)
                with gr.Row():
                    onboard_avg = gr.Number(label="Avg Daily Sale", value=5)
                    onboard_price = gr.Number(label="Price (₹)", value=5)
                onboard_add_btn = gr.Button("➕ Add Item", variant="primary")
        
        # Shared components below tabs (visible for both methods)
        onboard_status = gr.Textbox(label="Status", lines=3, interactive=False)
        onboard_inv_table = gr.DataFrame(label="📦 Your Inventory", interactive=False)
        onboard_finish_btn = gr.Button("✅ Finish Setup & Go to Dashboard", variant="primary", size="lg")
    
    # ═══════════════════════════════════════════════════════════
    # PAGE 3: MAIN DASHBOARD
    # ═══════════════════════════════════════════════════════════
    
    with gr.Column(visible=False) as dashboard_page:
        
        with gr.Row():
            gr.Markdown("## 📊 Your Shop Dashboard")
            logout_btn = gr.Button("🚪 Logout", size="sm")
        
        with gr.Tabs():
            
            # TAB 1: OCR Scanner
            with gr.Tab("📸 OCR Scanner"):
                gr.Markdown('<div class="sec">SCAN BILLS WITH OCR</div>')
                
                # Bill Type Selection (Sale or Purchase)
                ocr_mode = gr.Radio(
                    choices=["📉 Sale (Minus Stock)", "📈 Purchase (Add Stock)"],
                    value="📉 Sale (Minus Stock)",
                    label="Bill Type"
                )
                
                ocr_source = gr.Radio(["📸 Image", "✍️ Text"], value="📸 Image", label="Input Method")
                
                with gr.Row():
                    with gr.Column():
                        ocr_image = gr.Image(type="pil", label="Upload Bill Image")
                        ocr_text = gr.Textbox(label="Or Type/Paste Text", lines=4, visible=False)
                        ocr_scan_btn = gr.Button("🔍 Scan Now", variant="primary")
                    
                    with gr.Column():
                        ocr_status = gr.Textbox(label="Scan Status", lines=5, interactive=False)
                
                ocr_table = gr.DataFrame(label="✏️ Edit Items Before Confirming", interactive=True)
                ocr_confirm_btn = gr.Button("✅ Confirm Transaction", variant="primary", size="lg")
                ocr_confirm_status = gr.Textbox(label="Confirmation Status", interactive=False)
                
                # Toggle visibility based on source
                def toggle_ocr_input(source):
                    if source == "📸 Image":
                        return gr.update(visible=True), gr.update(visible=False)
                    else:
                        return gr.update(visible=False), gr.update(visible=True)
                
                ocr_source.change(toggle_ocr_input, inputs=[ocr_source], outputs=[ocr_image, ocr_text])
            
            # TAB 2: Inventory Management
            with gr.Tab("📦 Inventory"):
                gr.Markdown('<div class="sec">MANAGE YOUR STOCK</div>')
                
                inv_table = gr.DataFrame(label="Current Inventory", interactive=False)
                inv_refresh_btn = gr.Button("🔄 Refresh", size="sm")
                
                gr.Markdown("### ➕ Quick Actions")
                
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("**Record Manual Sale**")
                        sale_item = gr.Textbox(label="Item Name", placeholder="Pencil")
                        sale_qty = gr.Number(label="Quantity", value=1)
                        sale_btn = gr.Button("💰 Record Sale", variant="primary")
                        sale_status = gr.Textbox(label="Status", interactive=False)
                    
                    with gr.Column():
                        gr.Markdown("**Add Stock (Existing Item)**")
                        stock_item = gr.Textbox(label="Item Name", placeholder="Pencil")
                        stock_qty = gr.Number(label="Quantity", value=10)
                        stock_btn = gr.Button("📥 Add Stock", variant="primary")
                        stock_status = gr.Textbox(label="Status", interactive=False)
            
            # TAB 2.5: Add New Items (Bulk/Manual)
            with gr.Tab("➕ Add New Items"):
                gr.Markdown('<div class="sec">ADD INVENTORY ITEMS - BULK OR SINGLE</div>')
                
                with gr.Tabs():
                    # Sub-tab 1: Excel/CSV Upload
                    with gr.Tab("📄 Excel/CSV Upload"):
                        gr.Markdown("""
### 📋 Upload Inventory from Excel/CSV

Upload a spreadsheet file with your inventory items. The file must contain these exact columns:

| Column Name | Description | Example |
|-------------|-------------|---------|
| **Item Name** | Name of the item | Pencil, Pen Blue, Eraser |
| **Stock** | Current stock quantity | 50, 100, 25 |
| **Avg Daily Sale** | Average units sold per day | 5, 10, 3 |
| **Price** | Price in rupees (₹) | 5, 10, 3 |

**Format Requirements:**
- File format: `.csv` or `.xlsx`
- Column names must match exactly (case-sensitive)
- All values must be positive numbers
- Item Name cannot be empty

**Download Template:** [Sample CSV Template](#) *(Create a file with headers: Item Name,Stock,Avg Daily Sale,Price)*
                        """)
                        
                        excel_upload_file = gr.File(
                            label="Upload Excel/CSV File",
                            file_types=[".csv", ".xlsx", ".xls"],
                            type="filepath"
                        )
                        excel_upload_btn = gr.Button("📤 Upload & Import Items", variant="primary", size="lg")
                        excel_upload_status = gr.Textbox(label="Upload Status", lines=5, interactive=False)
                    
                    # Sub-tab 2: Single Manual Entry
                    with gr.Tab("✍️ Single Manual Entry"):
                        gr.Markdown("### Add One Item Manually")
                        gr.Markdown("Fill in the details below to add a single item to your inventory.")
                        
                        with gr.Row():
                            manual_new_name = gr.Textbox(label="Item Name", placeholder="e.g., Calculator")
                            manual_new_stock = gr.Number(label="Stock", value=10, precision=0)
                        with gr.Row():
                            manual_new_avg = gr.Number(label="Avg Daily Sale", value=2, precision=1)
                            manual_new_price = gr.Number(label="Price (₹)", value=200, precision=2)
                        
                        manual_add_btn = gr.Button("➕ Add Item to Inventory", variant="primary", size="lg")
                        manual_add_status = gr.Textbox(label="Status", interactive=False)
            
            # TAB 3: Predictions & Analytics
            with gr.Tab("📈 Predictions"):
                gr.Markdown('<div class="sec">AI-POWERED STOCK FORECASTING</div>')
                
                pred_run_btn = gr.Button("🚀 Generate Predictions", variant="primary", size="lg")
                pred_status = gr.Textbox(label="Status", interactive=False)
                
                pred_table = gr.DataFrame(label="30-Day Forecast", interactive=False)
                pred_dashboard = gr.Image(label="📊 Dashboard Overview", type="pil")
                
                gr.Markdown("### � ML Action Plan")
                pred_plan = gr.Textbox(label="Action Plan", lines=10, interactive=False, placeholder="Generate predictions to see action plan...")
                
                gr.Markdown("### 📱 Send Order via WhatsApp")
                with gr.Row():
                    wa_phone = gr.Textbox(label="Vendor Phone Number", placeholder="919876543210 (with country code)", scale=3)
                    wa_generate_btn = gr.Button("🔗 Generate WhatsApp Link", variant="primary", scale=1)
                wa_link_display = gr.HTML(label="WhatsApp Link")
                
                gr.Markdown("### Future Stock Projection")
                trend_item = gr.Textbox(label="Item Name", placeholder="Pencil")
                trend_btn = gr.Button("Show Future Stock Projection", variant="primary")
                trend_chart = gr.Image(label="Future Stock Projection Bar Chart", type="pil")
    
    # ═══════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═══════════════════════════════════════════════════════════
    
    # Auth Events
    login_btn.click(
        handle_login,
        inputs=[login_email, login_password],
        outputs=[login_status, user_session, auth_page, onboarding_page, dashboard_page]
    ).then(
        check_onboarding_status,
        inputs=[user_session],
        outputs=[auth_page, onboarding_page, dashboard_page]
    )
    
    signup_btn.click(
        handle_signup,
        inputs=[signup_email, signup_password],
        outputs=[signup_status, user_session, auth_page, onboarding_page, dashboard_page]
    ).then(
        check_onboarding_status,
        inputs=[user_session],
        outputs=[auth_page, onboarding_page, dashboard_page]
    )
    
    logout_btn.click(
        handle_logout,
        outputs=[login_status, user_session, auth_page, onboarding_page, dashboard_page]
    )
    
    # Onboarding Events
    onboard_excel_btn.click(
        handle_excel_upload,
        inputs=[user_session, onboard_excel_file],
        outputs=[onboard_status, onboard_inv_table]
    )
    
    onboard_add_btn.click(
        handle_add_onboarding_item,
        inputs=[user_session, onboard_name, onboard_stock, onboard_avg, onboard_price],
        outputs=[onboard_status, onboard_inv_table]
    )
    
    onboard_finish_btn.click(
        handle_finish_onboarding,
        inputs=[user_session],
        outputs=[onboard_status, onboarding_page, auth_page, dashboard_page]
    )
    
    # Dashboard Events - OCR Tab
    ocr_scan_btn.click(
        handle_ocr_scan,
        inputs=[user_session, ocr_image, ocr_text, ocr_source],
        outputs=[ocr_status, ocr_table]
    )
    
    ocr_confirm_btn.click(
        confirm_sales,
        inputs=[user_session, ocr_table, ocr_mode],
        outputs=[ocr_confirm_status, inv_table]
    )
    
    # Dashboard Events - Inventory Tab
    inv_refresh_btn.click(
        refresh_inventory,
        inputs=[user_session],
        outputs=[inv_table]
    )
    
    sale_btn.click(
        handle_manual_sale,
        inputs=[user_session, sale_item, sale_qty],
        outputs=[sale_status, inv_table]
    )
    
    stock_btn.click(
        handle_add_stock,
        inputs=[user_session, stock_item, stock_qty],
        outputs=[stock_status, inv_table]
    )
    
    # Dashboard Events - Add New Items Tab
    excel_upload_btn.click(
        handle_excel_upload,
        inputs=[user_session, excel_upload_file],
        outputs=[excel_upload_status, inv_table]
    )
    
    manual_add_btn.click(
        handle_add_new_item,
        inputs=[user_session, manual_new_name, manual_new_stock, manual_new_avg, manual_new_price],
        outputs=[manual_add_status, inv_table]
    )
    
    # Dashboard Events - Predictions Tab
    pred_run_btn.click(
        run_predictions,
        inputs=[user_session],
        outputs=[pred_status, pred_table, pred_dashboard, pred_plan]
    )
    
    wa_generate_btn.click(
        generate_wa_order_link,
        inputs=[user_session, pred_plan, wa_phone],
        outputs=[wa_link_display]
    )
    
    trend_btn.click(
        show_future_stock_projection,
        inputs=[user_session, trend_item],
        outputs=[trend_chart]
    )

# ═══════════════════════════════════════════════════════════
# LAUNCH APP
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🚀 StartingShop Mitra AI System...")
    app.launch(debug=True, share=True)
    
