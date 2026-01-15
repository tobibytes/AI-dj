#!/usr/bin/env python3
"""
Test script to simulate full mix generation flow with websocket monitoring
"""
import asyncio
import websockets
import json
import requests
import time

BACKEND_URL = "http://localhost:8000"

async def test_mix_generation():
    print("Testing mix generation with websocket progress monitoring...")

    # First, get Spotify access token
    try:
        response = requests.get(f"{BACKEND_URL}/spotify/auto-auth")
        response.raise_for_status()
        auth_data = response.json()
        access_token = auth_data.get("access_token")
        if not access_token:
            print("Failed to get Spotify access token")
            return
        print("Got Spotify access token")
    except Exception as e:
        print(f"Failed to get access token: {e}")
        return

    # Start mix generation FIRST to get session ID
    try:
        response = requests.post(
            f"{BACKEND_URL}/mix/generate",
            json={
                "prompt": "Create a chill electronic mix with downtempo beats",
                "duration_minutes": 2,
                "spotify_access_token": access_token
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
        )
        response.raise_for_status()
        mix_data = response.json()
        session_id = mix_data.get("session_id")
        if not session_id:
            print("Failed to get session ID")
            return
        print(f"Started mix generation with session ID: {session_id}")
    except Exception as e:
        print(f"Failed to start mix generation: {e}")
        return

    # IMMEDIATELY connect to websocket for progress updates
    uri = f"ws://localhost:8000/ws/mix/{session_id}"

    try:
        websocket = await websockets.connect(uri)
        print("Connected to websocket for progress updates")

        start_time = time.time()
        last_progress_time = start_time
        connected_received = False

        while time.time() - start_time < 300:  # 5 minute timeout
            try:
                # Set a reasonable timeout for receiving messages
                message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                current_time = time.time()

                try:
                    data = json.loads(message)
                    msg_type = data.get("type")

                    if msg_type == "connected":
                        print("✓ WebSocket connected and ready for progress updates")
                        connected_received = True
                    elif msg_type == "progress":
                        if not connected_received:
                            print("✓ WebSocket connected and ready for progress updates")
                            connected_received = True
                        progress_data = data.get("data", {})
                        stage = progress_data.get("stage", "unknown")
                        progress = progress_data.get("progress", 0)
                        detail = progress_data.get("detail", "")
                        print(".1f")
                        last_progress_time = current_time
                    elif msg_type == "complete":
                        complete_data = data.get("data", {})
                        cdn_url = complete_data.get("cdn_url", "")
                        duration = complete_data.get("duration_seconds", 0)
                        print(f"✓ Mix completed! Duration: {duration}s, URL: {cdn_url}")
                        await websocket.close()
                        return True
                    elif msg_type == "error":
                        error_msg = data.get("data", {}).get("error", "Unknown error")
                        print(f"✗ Mix generation failed: {error_msg}")
                        await websocket.close()
                        return False
                    else:
                        print(f"Received unknown message type: {msg_type}")

                except json.JSONDecodeError:
                    # This might be a binary ping/pong frame, ignore
                    pass

                # Check if we've been idle too long (no progress updates)
                if current_time - last_progress_time > 120:  # 2 minutes
                    print("⚠ No progress updates received for 2 minutes - connection may have stalled")
                    break

            except asyncio.TimeoutError:
                print("⚠ No message received within timeout period")
                break

        await websocket.close()
        print("Test completed - checking final status...")

    except Exception as e:
        print(f"WebSocket connection failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_mix_generation())
    if success:
        print("✓ Test passed - websocket connection maintained throughout mix generation")
    else:
        print("✗ Test failed - websocket issues detected")