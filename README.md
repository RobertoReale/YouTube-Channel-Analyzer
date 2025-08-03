# YouTube Channel Analyzer

A powerful desktop application for analyzing YouTube channels with advanced filtering, multi-API key support, and comprehensive video data extraction.

##  Features

### Core Functionality
- **Complete Channel Analysis**: Extract detailed information about any YouTube channel
- **Advanced Video Loading**: Three loading strategies (Fast, Smart, Complete) to optimize API usage
- **Multi-API Key Support**: Automatic rotation between multiple YouTube API keys to avoid quota limits
- **Smart Caching**: Efficient caching system to minimize redundant API calls
- **Session Management**: Save and resume analysis sessions

### Advanced Filtering
- **Keyword Search**: Search videos by title with support for:
  - Multiple keywords (AND/OR logic)
  - Exact phrases in quotes
  - Exclusion keywords with minus prefix
  - Case-sensitive and whole-word matching
- **Duration Filters**: Filter by video length with preset options (Shorts, Short, Medium, Long)
- **View Count Filters**: Filter videos by minimum view count
- **Date Range Filters**: Filter videos by publication date

### Data Export & Management
- **CSV Export**: Export complete or filtered video lists
- **Session Persistence**: Save analysis progress and resume later
- **Debug Information**: Comprehensive logging and debug tools
- **Performance Monitoring**: Track API usage and loading statistics

##  Requirements

- Python 3.7+
- YouTube Data API v3 key(s)
- Required Python packages (see Installation)

##  Installation

1. **Clone the repository**:
```bash
git clone https://github.com/yourusername/youtube-channel-analyzer.git
cd youtube-channel-analyzer
```

2. **Install required packages**:
```bash
pip install google-api-python-client pandas tkinter
```

3. **Get YouTube API Key(s)**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable YouTube Data API v3
   - Create credentials (API Key)
   - (Optional) Create multiple API keys for better quota management

##  Usage

### Quick Start

1. **Launch the application**:
```bash
python youtube_analyzer.py
```

2. **Configure API Key**:
   - Enter your YouTube API key in the designated field
   - Use "Save API Key" to persist configuration
   - Optionally add multiple keys via "Manage Keys"

3. **Analyze a Channel**:
   - Paste YouTube channel URL (supports multiple formats)
   - Click "Analyze Channel"
   - Choose loading strategy and click "Load Videos"

### Supported URL Formats

The analyzer supports various YouTube channel URL formats:
```
https://www.youtube.com/channel/UC_x5XG1OV2P6uZZ5FSM9Ttw
https://www.youtube.com/c/channelname
https://www.youtube.com/@username
https://www.youtube.com/user/username
```

### Loading Strategies

####  Fast Strategy
- **Best for**: Quick analysis, recent videos only
- **Loads**: ~3,000 most recent videos
- **API Calls**: ~60 calls
- **Time**: 1-2 minutes

####  Smart Strategy (Recommended)
- **Best for**: Balanced completeness and efficiency
- **Loads**: ~80% of channel videos
- **API Calls**: ~200 calls for large channels
- **Time**: 5-10 minutes
- **Features**: Adaptive algorithm based on channel size

####  Complete Strategy
- **Best for**: Maximum completeness, research purposes
- **Loads**: Attempts to find all videos
- **API Calls**: 500+ calls for large channels
- **Time**: 10-30+ minutes
- **Warning**: May hit API quotas, use multiple keys

### Advanced Filtering

#### Keyword Search Examples
```
# Single keyword
news

# Multiple keywords (all must be present)
news, politics, today

# At least one keyword present
news, politics (select "At least one" mode)

# Exact phrase
"breaking news"

# Exclude keywords
news, -sports, -entertainment

# Complex combination
"breaking news", politics, -sports
```

#### Duration Filters
- Enter duration as minutes: `5` (5 minutes)
- Enter as MM:SS format: `5:30` (5 minutes 30 seconds)
- Use preset buttons for common ranges

##  Understanding Results

### Channel Information Display
- Channel name and creation date
- Total subscriber count (if public)
- Total video count and view count
- Upload frequency analysis

### Video List Columns
- **Title**: Video title (click to search/filter)
- **Views**: Total view count
- **Likes**: Like count (if available)
- **Date**: Publication date
- **Duration**: Video length

### Performance Metrics
The status bar shows:
- Total videos loaded vs. declared
- Completeness percentage
- API calls used
- Loading strategy effectiveness

##  Configuration

### API Key Management
- **Single Key**: Basic usage with one API key
- **Multiple Keys**: Automatic rotation for heavy usage
- **Quota Management**: Smart switching when limits hit

### Settings File
Configuration is saved in `youtube_analyzer_config.json`:
```json
{
  "api_keys": ["key1", "key2", "key3"],
  "current_key": "key1"
}
```

## 🛠️ Troubleshooting

### Common Issues

#### "Quota Exceeded" Error
- **Solution**: Add more API keys or wait for quota reset
- **Prevention**: Use Smart strategy instead of Complete
- **Monitoring**: Check debug info for quota usage

#### Missing Videos
Large channels may have incomplete results due to:
- YouTube API limitations (~20K video limit via Playlist API)
- Private/unlisted videos not accessible
- Very old videos may not be indexed
- Deleted videos still counted in channel statistics

#### Slow Performance
- **Large Channels**: Use Fast or Smart strategy
- **Network Issues**: Check internet connection
- **API Limits**: Add more API keys for parallel processing

#### Channel Not Found
- Verify URL format is correct
- Check if channel is public
- Try different URL formats (@username vs /c/channel)

### Debug Information
Access via "🐛 Debug Info" button to see:
- API call statistics
- Loading strategy details
- Error logs and quota status
- Video distribution analysis

##  File Structure

```
youtube-channel-analyzer/
├── youtube_analyzer.py          # Main application
├── youtube_analyzer_config.json # Configuration file (auto-generated)
├── youtube_analyzer.log         # Log file (auto-generated)
├── *.session                    # Session files (user-generated)
└── README.md                    # This file
```

##  Session Management

### Saving Sessions
- Saves current analysis state
- Includes video cache and progress
- Allows resuming interrupted analysis

### Loading Sessions
- Resume previous analysis
- Continue from where you left off
- Merge with existing data

## 📈 Performance Tips

### For Large Channels (>10K videos)
1. **Use multiple API keys** for better quota management
2. **Start with Smart strategy** before trying Complete
3. **Save sessions frequently** to avoid losing progress
4. **Filter by date range** to focus on specific periods
5. **Consider channel characteristics** (news channels vs. personal channels)

### API Quota Optimization
- **Morning/Evening**: API quotas reset at midnight PT
- **Multiple Projects**: Create separate Google Cloud projects
- **Strategic Timing**: Plan analysis during low-usage periods

## 🤝 Contributing

We welcome contributions! Please feel free to submit:

- **Bug Reports**: Use GitHub issues with detailed reproduction steps
- **Feature Requests**: Describe use cases and expected behavior
- **Code Contributions**: Fork, create feature branch, submit PR
- **Documentation**: Help improve this README and code comments

### Development Setup
```bash
# Fork the repository
git clone https://github.com/yourusername/youtube-channel-analyzer.git
cd youtube-channel-analyzer

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/
```

##  License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

##  Disclaimer

This tool is for educational and research purposes. Please:
- Respect YouTube's Terms of Service
- Follow API usage guidelines
- Be mindful of quota limits
- Use responsibly and ethically

##  Support

- **Documentation**: Check this README first
- **Issues**: Use GitHub Issues for bug reports
- **Discussions**: Use GitHub Discussions for questions
- **API Help**: Refer to [YouTube Data API documentation](https://developers.google.com/youtube/v3)

---
