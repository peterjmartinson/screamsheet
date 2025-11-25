import json
import pytest
import os
from unittest.mock import patch, Mock
from src.nhl_screamsheet import get_game_scores_for_day  # Import your function

# 1. Create a fixture to load your saved JSON data
@pytest.fixture
def nhl_mock_data():
    # Adjust path to where you saved the file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(current_dir, 'fixtures', 'nhl_game_scores.json')
    
    with open(file_path, 'r') as f:
        return json.load(f)

# 2. The Test Function
def test_get_game_scores_success(nhl_mock_data):
    # We patch 'requests.get' inside the module where it is USED, not where it is defined
    # e.g., 'your_script_name.requests.get'
    with patch('requests.get') as mock_get:
        
        # --- The Mock Setup ---
        # Configure the mock to return a specific object
        mock_response = Mock()
        mock_response.status_code = 200
        # When .json() is called on the response, return our file data
        mock_response.json.return_value = nhl_mock_data 
        
        # Tell requests.get to return this mock_response
        mock_get.return_value = mock_response

        # --- Execute the Function ---
        results = get_game_scores_for_day("2023-11-23")

        # --- Assertions ---
        assert len(results) == 6
        assert results[0].away_team == "Carolina Hurricanes"
        assert results[0].home_score == 4
        assert results[0].status == "OFF"
        
        # Verify requests.get was called with the correct URL
        mock_get.assert_called_once_with("https://api-web.nhle.com/v1/schedule/2023-11-23")
