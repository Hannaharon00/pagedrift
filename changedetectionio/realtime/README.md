# Real-time Socket.IO Implementation

This directory contains the Socket.IO implementation for changedetection.io's real-time updates.

## Architecture Overview

The real-time system provides live updates to the web interface for:
- Watch status changes (checking, completed, errors)
- Queue length updates  
- General statistics updates

## Current Implementation

### Socket.IO Configuration
- **Async Mode**: `threading` (default) or `gevent` (optional via SOCKETIO_MODE env var)
- **Server**: Flask-SocketIO with threading support
- **Background Tasks**: Python threading with daemon threads

### Async Worker Integration
- **Workers**: Async workers using asyncio for watch processing
- **Queue**: AsyncSignalPriorityQueue for job distribution
- **Signals**: Blinker signals for real-time updates between workers and Socket.IO

### Environment Variables
- `SOCKETIO_MODE=threading` (default, recommended)
- `SOCKETIO_MODE=gevent` (optional, has cross-platform limitations)

