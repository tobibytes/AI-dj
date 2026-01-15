#!/usr/bin/env python3
"""
Simple websocket test script to verify heartbeat mechanism
"""
import asyncio
import websockets
import json
import time

async def test_websocket():
    uri = "ws://localhost:8000/ws/mix/test-session-123"

    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to websocket")

            # Send a test message
            await websocket.send(json.dumps({
                "type": "test",
                "data": {"message": "Hello from test client"}
            }))

            # Listen for messages and heartbeat pings
            start_time = time.time()
            message_count = 0

            while time.time() - start_time < 60:  # Run for 60 seconds
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=35.0)
                    message_count += 1
                    print(f"Received message {message_count}: {message}")

                    # If it's a ping, respond with pong
                    try:
                        data = json.loads(message)
                        if data.get("type") == "ping":
                            print("Received ping, responding with pong")
                            await websocket.send(json.dumps({"type": "pong"}))
                    except json.JSONDecodeError:
                        # Binary message (likely ping)
                        print("Received binary ping, responding with pong")
                        await websocket.pong(message)

                except asyncio.TimeoutError:
                    print("No message received in 35 seconds - heartbeat may have failed")
                    break

            print(f"Test completed. Received {message_count} messages in {time.time() - start_time:.1f} seconds")

    except Exception as e:
        print(f"WebSocket connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())