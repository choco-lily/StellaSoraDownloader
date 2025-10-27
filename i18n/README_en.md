# Stella Sora Downloader

A comprehensive GUI application for downloading Stella Sora game files from multiple servers with advanced comparison and selection features.

## Features

### 🌐 Multi-Server Support
- Support for multiple Stella Sora servers (KR, EN, JP, CN)
- Real-time server status checking
- Server-specific file size and hash comparison

### 📁 Advanced File Management
- **File Selection**: Choose specific files for download with checkboxes
- **Search Functionality**: Real-time search through file lists
- **Drag Selection**: Select multiple files by dragging
- **Bulk Operations**: Select All / Deselect All functionality

### 🔍 Server Comparison
- **Cross-Server Analysis**: Compare files across different servers
- **Hash Verification**: Check file integrity using MD5 hashes
- **Size Comparison**: Identify size differences between servers
- **Reference Server**: Set a reference server for comparison
- **Detailed File Information**: View server-specific file details

### 📊 Download Management
- **Progress Tracking**: Real-time download progress with speed indicators
- **Concurrent Downloads**: Parallel file downloads for faster completion
- **Error Handling**: Robust error handling with detailed logging
- **Resume Capability**: Continue interrupted downloads

### 💾 Data Persistence
- **Request Logging**: Save server requests by date and size
- **Configuration Storage**: Store server configurations for future use
- **Manifest Caching**: Cache file manifests for faster loading

## Screenshots

### Server Selection Window
![Server Selection](../example1.png)
- Select from available Stella Sora servers
- View server status and file counts
- Refresh server information

### File Download Selection
![File Selection](../example2.png)
- Browse and select files for download
- Use search to find specific files
- Drag to select multiple files
- View file sizes and hash values

### Download Progress
![Download Progress](../example3.png)
- Monitor download progress in real-time
- View current file being downloaded
- Track download speed and completion status

### Server Comparison
![Server Comparison](../example4.png)
- Compare files across different servers
- Set reference server for comparison
- View consistency status and differences

## Installation

### Prerequisites
- Python 3.7 or higher
- tkinter (usually included with Python)
- Required Python packages (see requirements.txt)

### Setup
1. Clone the repository:
```bash
git clone https://github.com/yourusername/StellaSoraDownloader.git
cd StellaSoraDownloader
```

2. Install required packages:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

## Usage

### Basic Workflow
1. **Launch Application**: Run `python main.py`
2. **Select Server**: Choose a server from the server selection window
3. **Choose Files**: Select files to download using checkboxes or drag selection
4. **Start Download**: Click "Download Selected" or "Download All"
5. **Monitor Progress**: Watch the download progress in the progress window

### Advanced Features

#### Server Comparison
1. Click "Compare Servers" in the server selection window
2. Use the search box to filter files
3. Set a reference server using the dropdown
4. Click "Apply Reference" to compare against the selected server
5. Double-click files to view detailed server-specific information

#### File Search
- Use the search box in any file list to filter files
- Search is case-insensitive and matches partial file paths
- Search results show filtered count vs total count

#### Drag Selection
- Click and drag to select multiple files
- Starting from a checked file will uncheck all files in the range
- Starting from an unchecked file will check all files in the range

## Configuration

### Server Settings
The application supports multiple servers defined in the `SERVERS` dictionary:
- **KR Server**: Korean Stella Sora server
- **EN Server**: English Stella Sora server  
- **JP Server**: Japanese Stella Sora server
- **CN Server**: Chinese Stella Sora server

### File Storage
- Downloaded files are saved to the selected directory
- Server request data is automatically saved by date and server
- Configuration files are cached for faster subsequent loads

## Technical Details

### Architecture
- **GUI Framework**: tkinter with ttk (Themed Tkinter)
- **Threading**: Background threads for server requests and downloads
- **HTTP Client**: requests library for API communication
- **Progress Tracking**: tqdm for download progress bars

### File Structure
```
StellaSoraDownloader/
├── main.py                 # Main application file
├── README.md              # This file
├── requirements.txt       # Python dependencies
└── [Server Folders]/     # Auto-generated server data folders
    └── [Size Folders]/   # Folders organized by file size
        ├── config_*.json
        ├── config2_*.json
        └── manifest_*.json
```

### API Integration
- **Authentication**: Custom authorization headers with server-specific salts
- **Configuration API**: Fetch game configuration and version information
- **Manifest API**: Download file manifests with hash and size information
- **File Download**: Direct file downloads from server CDN

## Error Handling

The application includes comprehensive error handling:
- **Network Errors**: Automatic retry with timeout handling
- **File Errors**: Graceful handling of file system errors
- **User Interruption**: Clean handling of Ctrl+C interruptions
- **Invalid Data**: Validation of server responses and file data

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue on GitHub
- Check the documentation
- Review the code comments for implementation details
