from flask import Flask, jsonify
import sys
import os
import asyncio
import json

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the clan info bot
from clan_info_bot import ClanInfoBot

app = Flask(__name__)

@app.route('/api/clan-data', methods=['GET'])
def get_clan_data():
    """API endpoint to get clan data"""
    try:
        # Run the async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get clan data from the bot
        clan_data = loop.run_until_complete(get_clan_data_async())
        
        if clan_data:
            return jsonify(clan_data)
        else:
            return jsonify({"error": "Failed to fetch clan data"}), 500
    except Exception as e:
        print(f"Error fetching clan data: {e}")
        return jsonify({"error": str(e)}), 500

async def get_clan_data_async():
    """Get clan data using the ClanInfoBot"""
    try:
        async with ClanInfoBot() as bot:
            # Get clan summary
            summary = await bot.get_clan_summary()
            return summary
    except Exception as e:
        print(f"Error in get_clan_data_async: {e}")
        return None

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Clan data server is running", "timestamp": "2025-10-22T11:30:00Z"})

@app.route('/health', methods=['GET'])
def health_check_extended():
    """Extended health check endpoint"""
    return jsonify({
        "status": "ok", 
        "message": "Clan data server is running",
        "service": "npt-clan-api",
        "version": "1.0.0"
    })

if __name__ == '__main__':
    # Get port from environment variable or default to 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)