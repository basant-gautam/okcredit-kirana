# 🏪 OKCredit Kirana - Shop Inventory & Sales Management System

A comprehensive Python-based shop inventory and sales management system powered by Google Gemini AI, designed specifically for small retail businesses (Kirana stores).

## 📋 Project Overview

This project provides an intelligent system for managing shop inventory, analyzing sales patterns, and generating AI-powered insights using Google's Gemini API. It's built as a Jupyter Notebook for easy experimentation and interactive analysis.

### Key Features

- 📦 **Inventory Management** - Track stock levels, reorder points, and pricing
- 📊 **Sales Analytics** - Analyze sales history and predict trends
- 🤖 **AI-Powered Insights** - Get intelligent recommendations using Google Gemini
- 🎯 **Smart Predictions** - Forecast future sales and inventory needs
- 📈 **Data Visualization** - Visual representation of sales patterns and inventory status

## 🛠️ Tech Stack

- **Python 3.x**
- **Google Generative AI (Gemini API)**
- **Pandas & NumPy** - Data manipulation and analysis
- **Matplotlib & OpenCV** - Data visualization
- **Scikit-learn** - Machine learning predictions
- **Tesseract OCR** - Document scanning (optional)
- **Gradio** - Web interface for interactivity

## 📦 Installation & Setup

### Prerequisites

- Python 3.8+
- Google Gemini API Key
- Jupyter Notebook or JupyterLab

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/okcredit-kirana.git
cd okcredit-kirana
```

### Step 2: Install Dependencies

```bash
pip install -q google-genai gradio pillow pandas numpy scikit-learn matplotlib opencv-python-headless
apt-get install -q tesseract-ocr  # For Linux/Colab
```

### Step 3: Set Up API Key

1. Get your Google Gemini API key from [Google AI Studio](https://aistudio.google.com/)
2. Open `okcredit (3).ipynb`
3. In Cell 2, replace the API key placeholder with your actual key:

```python
GEMINI_API_KEY = "YOUR_API_KEY_HERE"
```

## 🚀 Usage

### Running the Notebook

```bash
jupyter notebook "okcredit (3).ipynb"
```

### Workflow

1. **Cell 1** - Install all required libraries
2. **Cell 2** - Set up API keys and imports
3. **Cell 3+** - Initialize shop data and run analysis

## 📊 Features Breakdown

### Shop Data Management
- Initialize default inventory with stock levels, daily sales averages, reorder points, and prices
- Track sales history with timestamps and quantities
- Calculate inventory metrics and trends

### AI Analysis
- Generate insights using Google Gemini
- Get personalized recommendations for your shop
- Predict future inventory needs
- Analyze sales patterns and anomalies

### Predictions & Forecasting
- Machine Learning-based sales forecasting
- Inventory optimization suggestions
- Automatic reorder level recommendations

## 🗂️ Project Structure

```
okcredit-kirana/
├── README.md                    # This file
├── okcredit (3).ipynb          # Main Jupyter Notebook
└── .gitignore                   # Git ignore rules
```

## ⚙️ Configuration

Edit the inventory settings in Cell 3 to customize:
- Product names and stock levels
- Average daily sales
- Reorder points
- Product prices

## 🔒 Security Notes

⚠️ **IMPORTANT**: Never commit your API keys to GitHub!

1. Create a `.env` file (not tracked by git):
   ```
   GEMINI_API_KEY=your_key_here
   ```

2. Update `.gitignore`:
   ```
   .env
   *.ipynb_checkpoints
   __pycache__/
   ```

3. Load the key from environment:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
   ```

## 📝 Example Output

The system provides:
- 📈 Sales trend graphs
- 🎯 Stock level alerts
- 💡 AI-powered recommendations
- 📊 Inventory reports
- 🔮 Sales forecasts

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

## 📄 License

This project is open source and available under the MIT License.

## 👨‍💻 Author

Created for small retail businesses and Kirana store owners.

## 📞 Support

For issues and questions:
- Open an GitHub issue
- Check the notebook comments for inline documentation
- Review the cell-by-cell instructions in the notebook

---

**Happy Inventory Management! 🎉**

*"Apne shop ko intelligent banao - Make your shop smart with OKCredit Kirana!"*
app link https://okcredit-app-727763916674.asia-south1.run.app/