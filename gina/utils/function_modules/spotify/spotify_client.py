import os
import time
import html
import json
import base64
import socket
from logging import Logger
import spotipy
import requests
import subprocess
import webbrowser
from gina.utils.logger import setup_logger
from typing import Dict, Any, Optional
from dotenv import load_dotenv, set_key
from spotipy.oauth2 import SpotifyOAuth
from http.server import BaseHTTPRequestHandler, HTTPServer

logger: Logger = setup_logger()

class SpotifyClient:

    def __init__(self) -> None:
        """
        Initializes the SpotifyClient by loading environment variables, 
        setting up authentication, and creating an authenticated Spotify client.
        
        Raises:
        -------
        EnvironmentError:
            If required environment variables are missing.
        spotipy.SpotifyException:
            If authentication fails.
        """
        try:
            # Load environment variables from .env file
            load_dotenv()

            # Retrieve Spotify credentials from environment variables
            client_id = os.getenv('SPOTIFY_CLIENT_ID')
            client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
            redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI')
            self.default_device_id = os.getenv('SPOTIFY_DEFAULT_DEVICE_ID')

            # Ensure all required environment variables are loaded
            if not client_id or not client_secret or not redirect_uri:
                raise EnvironmentError("Spotify API credentials not found in environment variables.")

            # Set up the Spotify authentication manager
            self.auth_manager = SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope='user-read-playback-state user-modify-playback-state user-read-currently-playing user-read-recently-played playlist-modify-public playlist-modify-private ugc-image-upload user-library-read user-library-modify user-top-read user-read-private user-read-email',
            )

            # Create an authenticated Spotify client
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

            # Fetch and save default device ID if not set
            if not self.default_device_id:
                print("No default device ID found. Fetching available devices...")
                self.default_device_id = self.fetch_default_device_id()
            
            self.auth()
            print("SpotifyClient initialized successfully.")
                
        except Exception as e:
            logger.exception("Failed to initialize SpotifyClient: %s", e)
            raise

    class WebHandler(BaseHTTPRequestHandler):
        def __init__(self, auth_manager, token_info_callback, *args, **kwargs):
            self.auth_manager = auth_manager
            self.token_info_callback = token_info_callback
            super().__init__(*args, **kwargs)

        def do_GET(self):
            """
            Handles GET requests and retrieves access tokens for authentication.

            Extracts authorization code from the callback URL and fetches access token using
            the Spotify OAuth manager. Calls a callback with token info if successful.
            """
            if self.path.startswith('/callback'):
                try:
                    code = self.path.split('=')[1]
                    token_info = self.auth_manager.get_access_token(code)
                    self.token_info_callback(token_info)

                    # Send response back to the user
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'Authentication successful! You can close this window now.')
                
                except IndexError:
                    logger.error("Invalid callback URL format.")
                    self.send_error(400, "Invalid request format.")
                
                except Exception as e:
                    logger.exception("Unexpected error during authentication callback. %s", e)
                    self.send_error(500, "Internal server error.")

    def load_cached_token(self, cache_path: str = '.cache') -> Optional[Dict[str, Any]]:
        """
        Loads token information from a cache file, if available.

        Parameters:
        -----------
        cache_path : str
            Path to the cache file containing token information. Default is '.cache'.

        Returns:
        --------
        dict or None:
            A dictionary containing token information if the file is read successfully,
            None if the file is not found or if there is an error reading the file.

        Raises:
        -------
        IOError:
            If there is an error opening or reading the file, excluding FileNotFoundError.
        """
        try:
            with open(cache_path, 'r') as f:
                token_info = json.load(f)
                logger.debug(
                    f"Token information successfully loaded from '{cache_path}'."
                )
                return token_info

        except FileNotFoundError:
            logger.warning(f"Cache file '{cache_path}' not found. Returning None.")
            return None

        except json.JSONDecodeError:
            logger.error(f"Cache file '{cache_path}' is not valid JSON. Returning None.")
            return None

        except IOError as e:
            logger.exception(f"Error reading cache file '{cache_path}': {e}")
            raise

    def auth(self):
        """
        Authenticates the user with Spotify, opening the authorization URL in a web browser
        if no cached token is found. The HTTP server listens for a response containing the
        authorization code, which is used to obtain an access token.

        Raises:
        -------
        Exception:
            Any error during the authentication process.
        """
        try:
            # Define a token handling function to store the received token info
            def handle_token(token_info):
                self.token_info = token_info

            # Attempt to load token from cache
            self.token_info = self.load_cached_token()

            # If no cached token is found, start the authentication flow
            if self.token_info is None:
                logger.debug("No cached token found, initiating new authentication flow.")

                # Start HTTP server to listen for callback
                httpd = HTTPServer(('localhost', 8888), lambda *args, **kwargs: 
                                self.WebHandler(self.auth_manager, handle_token, *args, **kwargs))

                # Generate the authorization URL and open it in the user's browser
                try:
                    auth_url = self.auth_manager.get_authorize_url()
                    webbrowser.open(auth_url)
                    logger.debug("Opened browser for user authentication.")
                except Exception as browser_error:
                    logger.error(f"Failed to open browser for authentication: {browser_error}")
                    raise

                # Handle the incoming request to capture the authorization response
                print("Waiting for user to authorize application...")
                httpd.handle_request()
                print("Authorization process completed.")

            else:
                print("Cached token found, skipping authentication.")

        except Exception as e:
            logger.exception("Error during authentication: %s", e)
            raise
    
    def player(func):
        func._is_player_function = True
        return func

    def search(func):
        func._is_search_function = True
        return func

    def playlists(func):
        func._is_playlists_function = True
        return func

    def tracks(func):
        func._is_tracks_function = True
        return func

    def albums(func):
        func._is_albums_function = True
        return func

    def users(func):
        func._is_users_function = True
        return func

    def custom(func):
        func._is_custom_function = True
        return func

    @custom
    def fetch_default_device_id(self) -> str:
        """
        Fetches the default device ID for Spotify playback. If no device is found,
        launches Spotify and retries.

        Returns:
        --------
        str:
            The default device ID if found.

        Raises:
        -------
        Exception:
            If no default device ID could be determined.
        """
        try:
            # Get the computer's hostname in lowercase
            computer_name = socket.gethostname().lower()
            
            # Fetch available devices
            devices = self.sp.devices().get('devices', [])
            
            # Retry with Spotify app launch if no devices found
            if not devices:
                logger.warning("No devices found. Launching Spotify app and retrying.")
                self.launch_spotify_app()
                time.sleep(5)  # Adjust delay as needed
                devices = self.sp.devices().get('devices', [])

            # Search for a device that matches the computer's hostname, case-insensitively
            for device in devices:
                if device['name'].lower() == computer_name:
                    default_device_id = device['id']
                    set_key(".env", "SPOTIFY_DEFAULT_DEVICE_ID", default_device_id)
                    print(f"Default device ID found and saved: {default_device_id}")
                    return default_device_id

            raise Exception("No matching device found for this computer.")
            
        except Exception as e:
            logger.error(f"Error fetching default device ID: {e}")
            raise

    @player
    def fetch_available_devices(self, args = None) -> str:
        """
        Retrieves the list of available Spotify devices.

        Parameters:
        -----------
        args : dict, optional
            Additional parameters if required in the future.

        Returns:
        --------
        str:
            A message with the result or an error message if unable to retrieve devices.

        Raises:
        -------
        Exception:
            If there is an error retrieving devices.
        """
        try:
            result = self.sp.devices()
            logger.info("Fetched available Spotify devices")
            return f"Result: {result}"
        except Exception as e:
            error_message = f"Error fetching available devices: {str(e)}"
            logger.error(error_message)
            return "Error fetching available devices."

    @player
    def fetch_playback_state(self, args: dict = None) -> str:
        """
        Retrieves and formats the current playback state information from Spotify.

        Parameters:
        -----------
        params : dict, optional
            Additional parameters for the function, if needed in the future.

        Returns:
        --------
        str:
            A formatted string with playback details, or a message if no playback is active.

        Raises:
        -------
        Exception:
            If there is an error retrieving playback information.
        """
        try:
            # Retrieve current playback information from Spotify
            playback_info: dict = self.sp.current_playback()
            if playback_info:
                print(type(playback_info))
                if not playback_info.get('item'):
                    logger.info("No active playback found.")
                    return "No active playback."
            else: 
                logger.info("No active playback found.")
                return "No active playback."

            # Extract main playback details
            track_name = playback_info['item']['name']
            artist_name = playback_info['item']['artists'][0]['name']
            album_name = playback_info['item']['album']['name']
            is_playing = playback_info['is_playing']
            progress_ms = playback_info['progress_ms']
            duration_ms = playback_info['item']['duration_ms']

            # Additional details from device
            device_info = playback_info.get('device', {})
            device_name = device_info.get('name', 'Unknown Device')
            device_type = device_info.get('type', 'Unknown Type')
            volume_percent = device_info.get('volume_percent', 'Unknown Volume')

            # Playback controls
            shuffle_state = playback_info.get('shuffle_state', False)
            repeat_state = playback_info.get('repeat_state', 'off')

            # Context information
            context_info = playback_info.get('context', {})
            if context_info:
                context_type = context_info.get('type', 'Unknown')
                context_url = context_info.get('external_urls', {}).get('spotify', 'N/A')

            # Additional track details
            is_explicit = playback_info['item'].get('explicit', False)
            popularity = playback_info['item'].get('popularity', 'Unknown')
            track_url = playback_info['item']['external_urls'].get('spotify', 'No Track URL')
            release_date = playback_info['item']['album'].get('release_date', 'Unknown Release Date')

            # Format progress and duration from milliseconds to minutes:seconds
            progress = f"{progress_ms // 60000}:{(progress_ms // 1000) % 60:02}"
            duration = f"{duration_ms // 60000}:{(duration_ms // 1000) % 60:02}"

            # Format the result string with all the details
            result_str = (
                f"Device: {device_name} ({device_type}) - Volume: {volume_percent}%\n"
                f"Track: {track_name}\n"
                f"Artist: {artist_name}\n"
                f"Album: {album_name} - Released: {release_date}\n"
                f"Explicit: {'Yes' if is_explicit else 'No'}\n"
                f"Popularity: {popularity}\n"
                f"Playback Position: {progress} / {duration}\n"
                f"Currently Playing: {'Yes' if is_playing else 'No'}\n"
                f"Shuffle: {'On' if shuffle_state else 'Off'}\n"
                f"Repeat Mode: {repeat_state}\n"
                f"Track URL: {track_url}\n"
            )

            try:
                if context_type:
                    result_str += f"Context: {context_type} - {context_url}\n"
            except NameError:
                pass

            logger.info("Playback information retrieved successfully.")
            return result_str

        except Exception as e:
            logger.error("Error retrieving playback state: %s", e)
            return "An error occurred while retrieving playback information."

    @player
    def transfer_playback(self, args = None) -> str:
        """
        Transfers Spotify playback to a specified device.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing the device ID for playback transfer.

        Returns:
        --------
        str:
            A message indicating success or failure of transferring playback.
        """
        try:
            device_id = args.get("device_id") if args else None
            if not device_id:
                logger.warning("Device ID not provided for transfer playback.")
                return "Device ID is required to transfer playback."

            self.sp.transfer_playback(device_id)
            result_message = "Transferred Spotify Playback"
            logger.info(result_message)
            return result_message

        except Exception as e:
            error_message = f"Error transferring playback: {str(e)}"
            logger.error(error_message)
            return error_message

    def launch_spotify_app(self, args = None) -> str:
        """
        Launches the Spotify application on Windows.

        Returns:
        --------
        str:
            A message indicating success or failure of launching the Spotify app.

        Raises:
        -------
        Exception:
            If there is an error launching the app.
        """
        try:
            # Path to Spotify's default installation location on Windows
            spotify_path = "C:\\Users\\{USERNAME}\\AppData\\Roaming\\Spotify\\Spotify.exe"

            # Replace {USERNAME} with the current user's name
            spotify_path = spotify_path.replace("{USERNAME}", os.getlogin())

            # Attempt to launch Spotify
            subprocess.Popen(spotify_path)
            logger.info("Spotify app launched successfully.")
            return "Spotify app launched successfully."

        except FileNotFoundError:
            error_message = "Spotify app not found at the default location."
            logger.error(error_message)
            return error_message

        except Exception as e:
            error_message = f"Error launching Spotify app: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def start_playback(self, args: dict = None) -> str:
        """
        Starts Spotify playback with the specified track URIs or context URI if provided.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing playback options. Supports:
                - 'uris' (list): List of track URIs.
                - 'context_uri' (str): URI of the context (album, artist, or playlist).

        Returns:
        --------
        str:
            A message indicating success or failure of starting playback.

        Raises:
        -------
        Exception:
            If there is an error starting playback.
        """
        try:
            # Extract URIs or context URI
            uris = args.get("uris") if args and "uris" in args else None
            context_uri = args.get("context_uri") if args and "context_uri" in args else None

            # Attempt to start playback using Spotify API
            result = self.sp.start_playback(uris=uris, context_uri=context_uri)

            # Check result and provide user feedback
            if result is None:
                result_message = "Started Spotify Playback"
                logger.info(result_message)
                return result_message

        except Exception as e:
            error_message = "Error starting playback."
            logger.error(f"{error_message}: {e}")

            # Check if the error is due to no active device
            if "NO_ACTIVE_DEVICE" in str(e):
                try:
                    logger.warning("No active device found. Retrying with default device.")
                    result = self.sp.start_playback(uris=uris, context_uri=context_uri, device_id=self.default_device_id)

                    if result is None:
                        result_message = "Started Spotify Playback on default device"
                        logger.info(result_message)
                        return result_message

                except Exception as retry_error:
                    logger.error(f"Retry failed: {retry_error}. Launching Spotify app and retrying playback.")
                    launch_result = self.launch_spotify_app()
                    logger.info(f"Spotify app launch result: {launch_result}")

                    # Retry with a few attempts and delay
                    for attempt in range(1, 4):
                        logger.info(f"Attempt {attempt}: Retrying after launching Spotify app...")
                        time.sleep(3)

                        try:
                            result = self.sp.start_playback(uris=uris, context_uri=context_uri, device_id=self.default_device_id)
                            if result is None:
                                result_message = "Started Spotify Playback on default device after launching app"
                                logger.info(result_message)
                                return result_message
                        except Exception as final_error:
                            logger.warning(f"Attempt {attempt} failed: {final_error}")

                    final_error_message = "Failed to start playback after launching Spotify app and multiple retry attempts."
                    logger.error(final_error_message)
                    return final_error_message

            return error_message

    @player
    def pause_playback(self, args = None) -> str:
        """
        Pauses Spotify playback.

        Parameters:
        -----------
        args : dict
            Additional parameters if required in the future.

        Returns:
        --------
        str:
            A message indicating success or failure of pausing playback.

        Raises:
        -------
        Exception:
            If there is an error pausing playback.
        """
        try:
            result = self.sp.pause_playback()
            if result is None:
                result_message = "Paused Spotify Playback"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error pausing playback: {str(e)}"
            logger.error(error_message)
            return "Error pausing playback."

    @player
    def skip_to_next(self, args = None) -> str:
        try:
            result = self.sp.next_track()
            if result is None:
                result_message = "Skipped to Next song on Spotify"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error skipping to next track: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def skip_to_previous(self, args = None) -> str:
        try:
            result = self.sp.previous_track()
            if result is None:
                result_message = "Skipped to Previous song on Spotify"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error skipping to previous track: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def seek_to_position(self, args = None) -> str:
        try:
            position_ms = args.get("position_ms") if args else None
            result = self.sp.seek_track(position_ms)
            if result is None:
                result_message = f"Seeked to {position_ms} ms in current Spotify track"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error seeking to position: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def set_repeat_mode(self, args = None) -> str:
        try:
            state = args.get("state") if args else None
            result = self.sp.repeat(state)
            if result is None:
                result_message = f"Set repeat mode to {state} on Spotify"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error setting repeat mode: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def set_playback_volume(self, args = None) -> str:
        try:
            volume_percent = args.get("volume_percent") if args else None
            result = self.sp.volume(volume_percent)
            if result is None:
                result_message = f"Set playback volume to {volume_percent}% on Spotify"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error setting playback volume: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def toggle_playlist_shuffle(self, args = None) -> str:
        try:
            state = args.get("state") if args else None
            result = self.sp.shuffle(state)
            if result is None:
                result_message = f"Shuffle state set to {state} on Spotify"
                logger.info(result_message)
                return result_message
        except Exception as e:
            error_message = f"Error toggling playlist shuffle: {str(e)}"
            logger.error(error_message)
            return error_message

    @player
    def get_recently_played_tracks(self, args = None) -> str:
        try:
            limit = args.get("limit", 50) if args else 50
            recently_played_info = self.sp.current_user_recently_played(limit=limit)
            if not recently_played_info or not recently_played_info.get('items'):
                logger.info("No recently played tracks found on Spotify.")
                return "No recently played tracks."

            recently_played_tracks_info = []
            for item in recently_played_info['items']:
                track = item['track']
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                album_name = track['album']['name']
                played_at = item['played_at']
                recently_played_tracks_info.append(
                    f"Track: {track_name}, Artist: {artist_name}, Album: {album_name}, Played At: {played_at}"
                )

            result_str = '\n'.join(recently_played_tracks_info)
            logger.info("Fetched Recently Played Spotify Tracks")
            return result_str
        except Exception as e:
            logger.error(f"Error getting recently played tracks: {str(e)}")
            return "Error getting recently played tracks."

    @player
    def get_user_queue(self, args = None) -> str:
        try:
            queue_info = self.sp.queue()
            if not queue_info or not queue_info.get('items'):
                logger.info("No items in the Spotify queue.")
                return "No items in the queue."

            queue_tracks_info = []
            for track in queue_info['items']:
                track_name = track['name']
                artist_name = track['artists'][0]['name']
                album_name = track['album']['name']
                queue_tracks_info.append(f"Track: {track_name}, Artist: {artist_name}, Album: {album_name}")

            result_str = '\n'.join(queue_tracks_info)
            logger.info("Fetched Current Spotify Queue")
            return result_str
        except Exception as e:
            logger.error(f"Error getting user queue: {str(e)}")
            return "Error getting user queue."

    @player
    def add_item_to_playback_queue(self, args = None) -> str:
        try:
            uri = args.get("uri") if args else None
            result = self.sp.add_to_queue(uri)
            if result is None:
                result_message = f"Added the song {uri} to the playback queue"
                logger.info(result_message)
                return result_message
        except Exception as e:
            logger.error(f"Error adding item to playback queue: {str(e)}")
            return "Error adding item to playback queue."
    
    @search
    def search_track(self, args = None) -> str:
        """
        Searches for tracks, artists, and albums on Spotify based on the provided query with optional filters.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing search parameters:
                - 'q' (str): The search query. Supports field filters like artist, album, year, genre.
                - 'limit' (int): Number of results to return.
                - 'type' (str, optional): Type of search, defaults to "track,artist,album".

        Returns:
        --------
        str:
            Formatted search results or a message if no results are found.
        """
        try:
            base_query = args.get('q', "") if args else ""
            filters = args.get('filters', {})
            limit = args.get('limit', 10)
            search_type = args.get("type", "track,artist,album")

            # Add filters to the base query
            for key, value in filters.items():
                base_query += f" {key}:{value}"

            result = self.sp.search(q=base_query, limit=limit, type=search_type)
            
            output = []

            # Tracks
            if 'tracks' in result and result['tracks']['items']:
                output.append("Tracks:")
                for track in result['tracks']['items']:
                    track_name = track['name']
                    artist_name = track['artists'][0]['name']
                    album_name = track['album']['name']
                    track_url = track['external_urls']['spotify']
                    output.append(f"Track: {track_name}, Artist: {artist_name}, Album: {album_name}, URL: {track_url}")

            # Artists
            if 'artists' in result and result['artists']['items']:
                output.append("\nArtists:")
                for artist in result['artists']['items']:
                    artist_name = artist['name']
                    artist_url = artist['external_urls']['spotify']
                    output.append(f"Artist: {artist_name}, URL: {artist_url}")

            # Albums
            if 'albums' in result and result['albums']['items']:
                output.append("\nAlbums:")
                for album in result['albums']['items']:
                    album_name = album['name']
                    artist_name = album['artists'][0]['name']
                    album_url = album['external_urls']['spotify']
                    output.append(f"Album: {album_name}, Artist: {artist_name}, URL: {album_url}")

            return '\n'.join(output) if output else "No results found."

        except Exception as e:
            logger.error(f"Error searching: {str(e)}")
            return "Error searching."
    
    @playlists
    def get_playlist(self, args=None) -> str:
        """
        Retrieves and formats essential information from a Spotify playlist.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'playlist_id' (str): ID of the playlist to retrieve.

        Returns:
        --------
        str:
            Formatted playlist information or an error message.
        """
        try:
            playlist_id = args.get("playlist_id") if args else None
            if not playlist_id:
                return "Playlist ID is required."

            # Fetch playlist info
            playlist_info = self.sp.playlist(playlist_id)

            # Extract relevant information and decode any HTML entities
            name = html.unescape(playlist_info.get("name", "Unknown"))
            description = html.unescape(playlist_info.get("description", "No description available"))
            followers = playlist_info.get("followers", {}).get("total", 0)
            collaborative = "Yes" if playlist_info.get("collaborative", False) else "No"
            public = "Yes" if playlist_info.get("public", False) else "No"
            playlist_url = playlist_info.get("external_urls", {}).get("spotify", "No URL available")
            owner_name = html.unescape(playlist_info.get("owner", {}).get("display_name", "Unknown"))
            owner_url = playlist_info.get("owner", {}).get("external_urls", {}).get("spotify", "No URL available")
            image_url = playlist_info.get("images", [{}])[0].get("url", "No image available")

            # Base playlist information
            result_str = (
                f"Playlist Name: {name}\n"
                f"Description: {description}\n"
                f"Followers: {followers}\n"
                f"Collaborative: {collaborative}\n"
                f"Public: {public}\n"
                f"Playlist URL: {playlist_url}\n"
                f"Owner: {owner_name} ({owner_url})\n"
                f"Image: {image_url}"
            )

            return result_str

        except Exception as e:
            logger.error(f"Error fetching playlist: {str(e)}")
            return "Error fetching playlist."

    @playlists
    def change_playlist_details(self, args=None) -> str:
        """
        Changes details of a Spotify playlist.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing the playlist modification details:
                - 'playlist_id' (str): ID of the playlist to modify.
                - 'name' (str, optional): New name for the playlist.
                - 'description' (str, optional): New description for the playlist.
                - 'public' (bool, optional): Whether the playlist is public.
                - 'collaborative' (bool, optional): Whether the playlist is collaborative.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            if not args or not args.get("playlist_id"):
                return "Playlist ID is required."

            self.sp.playlist_change_details(
                playlist_id=args.get("playlist_id"),
                name=args.get("name"),
                description=args.get("description"),
                public=args.get("public"),
                collaborative=args.get("collaborative")
            )
            return "Playlist details updated successfully."

        except Exception as e:
            logger.error(f"Error changing playlist details: {str(e)}")
            return "Error changing playlist details."
        
    @playlists
    def get_playlist_items(self, args=None) -> str:
        """
        Retrieves items (tracks) from a Spotify playlist.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'playlist_id' (str): ID of the playlist to retrieve items from.
                - 'limit' (int, optional): Number of items to retrieve (default: 100).
                - 'offset' (int, optional): Starting point for items (default: 0).

        Returns:
        --------
        str:
            Playlist items information or an error message.
        """
        try:
            playlist_id = args.get("playlist_id") if args else None
            limit = args.get("limit", 100)
            offset = args.get("offset", 0)

            if not playlist_id:
                return "Playlist ID is required."

            # Fetch playlist items
            items = self.sp.playlist_items(playlist_id, limit=limit, offset=offset)

            # Check if items are present
            if not items or 'items' not in items or len(items['items']) == 0:
                return "No items found in the playlist."

            # Format track information
            tracks_info = []
            for item in items['items']:
                track = item.get('track')
                if track:
                    track_name = track.get('name', 'Unknown Track')
                    artist_name = track['artists'][0]['name'] if track.get('artists') else 'Unknown Artist'
                    album_name = track['album']['name'] if track.get('album') else 'Unknown Album'
                    album_url = track['album']['external_urls']['spotify'] if track.get('album') and track['album'].get('external_urls') else 'No Album URL'
                    track_url = track['external_urls']['spotify'] if track.get('external_urls') else 'No URL'
                    
                    tracks_info.append(
                        f"Track: {track_name}, Artist: {artist_name}, Album: {album_name}, "
                        f"Album URL: {album_url}, Track URL: {track_url}"
                    )

            return '\n'.join(tracks_info)

        except Exception as e:
            logger.error(f"Error retrieving playlist items: {str(e)}")
            return "Error retrieving playlist items."

    @playlists
    def add_item_to_playlist(self, args=None) -> str:
        """
        Adds an item (track) to a Spotify playlist.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'playlist_id' (str): ID of the playlist to add the item to.
                - 'uri' (str): URI of the item to add.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            playlist_id = args.get("playlist_id") if args else None
            uri = args.get("uri") if args else None

            if not playlist_id or not uri:
                return "Playlist ID and URI are required."

            self.sp.playlist_add_items(playlist_id, [uri])
            return "Item added to the playlist successfully."

        except Exception as e:
            logger.error(f"Error adding item to playlist: {str(e)}")
            return "Error adding item to playlist."

    @playlists
    def remove_playlist_items(self, args=None) -> str:
        """
        Removes items (tracks) from a Spotify playlist.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'playlist_id' (str): ID of the playlist to remove items from.
                - 'uris' (list): List of URIs of items to remove.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            playlist_id = args.get("playlist_id") if args else None
            uris = args.get("uris") if args else None

            if not playlist_id:
                return "Playlist ID is required."
            if not uris or not isinstance(uris, list):
                return "URIs must be a non-empty list."

            self.sp.playlist_remove_all_occurrences_of_items(playlist_id, uris)
            logger.info(f"Successfully removed items from playlist {playlist_id}.")
            return "Items removed from the playlist successfully."

        except Exception as e:
            logger.error(f"Error removing playlist items: {str(e)}")
            return "Error removing playlist items."

    @playlists
    def get_current_user_playlists(self, args=None) -> str:
        """
        Retrieves a list of playlists for the current Spotify user.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'offset' (int): Starting point for playlists.
                - 'limit' (int): Number of playlists to retrieve per request.

        Returns:
        --------
        str:
            A formatted list of playlists or an error message.
        """
        try:
            playlists = []
            offset = args.get("offset", 0) if args else 0
            limit = args.get("limit", 20) if args else 20

            # Paginate through all user playlists
            while True:
                playlists_info = self.sp.current_user_playlists(offset=offset, limit=limit)
                if not playlists_info or not playlists_info.get('items'):
                    if offset == 0:
                        return "No playlists found."
                    break

                for playlist in playlists_info['items']:
                    playlist_name = playlist['name']
                    playlist_id = playlist['id']
                    playlist_url = playlist['external_urls']['spotify']
                    playlists.append(f"Playlist: {playlist_name}, ID: {playlist_id}, URL: {playlist_url}")

                # Increment offset to fetch the next batch if needed
                offset += limit
                if len(playlists_info['items']) < limit:
                    break

            return '\n'.join(playlists) if playlists else "No playlists found."

        except Exception as e:
            logger.error(f"Error fetching user playlists: {str(e)}")
            return "Error fetching user playlists."

    @playlists
    def get_user_playlists(self, args=None) -> str:
        """
        Retrieves a list of playlists for a Spotify user.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'user_id' (str): ID of the user to fetch playlists for.
                - 'offset' (int): Starting point for playlists.
                - 'limit' (int): Number of playlists to retrieve per request.

        Returns:
        --------
        str:
            A formatted list of playlists or an error message.
        """
        try:
            user_id = args.get("user_id") if args else None
            offset = args.get("offset", 0) if args else 0
            limit = args.get("limit", 20) if args else 20

            if not user_id:
                return "User ID is required."

            playlists = []
            while True:
                playlists_info = self.sp.user_playlists(user_id, offset=offset, limit=limit)
                if not playlists_info or not playlists_info.get('items'):
                    if offset == 0:
                        return "No playlists found."
                    break

                for playlist in playlists_info['items']:
                    playlist_name = playlist['name']
                    playlist_id = playlist['id']
                    playlist_url = playlist['external_urls']['spotify']
                    playlists.append(f"Playlist: {playlist_name}, ID: {playlist_id}, URL: {playlist_url}")

                # Increment offset to fetch the next batch if needed
                offset += limit
                if len(playlists_info['items']) < limit:
                    break

            return '\n'.join(playlists) if playlists else "No playlists found."

        except Exception as e:
            logger.error(f"Error fetching user playlists: {str(e)}")
            return "Error fetching user playlists."

    @playlists
    def create_playlist(self, args=None) -> str:
        """
        Creates a new Spotify playlist for the current user.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'name' (str): Name of the new playlist.
                - 'description' (str, optional): Description of the new playlist.
                - 'public' (bool, optional): Whether the playlist is public.
                - 'collaborative' (bool, optional): Whether the playlist is collaborative.

        Returns:
        --------
        str:
            Success message with playlist details or an error message.
        """
        try:
            name = args.get("name") if args else None
            if not name:
                return "Playlist name is required."

            description = args.get("description", "")
            public = args.get("public", True)
            collaborative = args.get("collaborative", False)

            # Create the playlist
            result = self.sp.user_playlist_create(
                self.sp.me()['id'], name, public=public, collaborative=collaborative, description=description
            )

            if result:
                playlist_name = result['name']
                playlist_id = result['id']
                playlist_url = result['external_urls']['spotify']
                return f"Playlist '{playlist_name}' created successfully. ID: {playlist_id}, URL: {playlist_url}"

        except Exception as e:
            logger.error(f"Error creating playlist: {str(e)}")
            return "Error creating playlist."

    @playlists
    def get_featured_playlists(self, args=None) -> str:
        """
        Retrieves a list of featured playlists on Spotify.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'limit' (int): Number of playlists to retrieve.
                - 'country' (str, optional): Country code for featured playlists.
                - 'locale' (str, optional): Locale for featured playlists.

        Returns:
        --------
        str:
            A formatted list of featured playlists or an error message.
        """
        try:
            limit = min(max(args.get("limit", 10), 1), 50) if args else 10
            country = args.get("country") if args else None
            locale = args.get("locale") if args else None

            featured = self.sp.featured_playlists(limit=limit, country=country, locale=locale)
            if not featured or not featured.get('playlists'):
                return "No featured playlists found."

            message = featured.get("message", "Featured Playlists:")
            playlists_info = [message]

            for playlist in featured['playlists']['items']:
                playlist_name = playlist['name']
                playlist_url = playlist['external_urls']['spotify']
                playlists_info.append(f"Playlist: {playlist_name}, URL: {playlist_url}")

            return '\n'.join(playlists_info)

        except Exception as e:
            logger.error(f"Error fetching featured playlists: {str(e)}")
            return "Error fetching featured playlists."

    @playlists
    def add_custom_cover_image(self, args=None) -> str:
        """
        Adds a custom cover image to a Spotify playlist from a URL or local file path.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'playlist_id' (str): ID of the playlist to add the image to.
                - 'image_url' (str, optional): URL of the image to use as the cover.
                - 'image_path' (str, optional): Local file path of the image to use as the cover.

            Only one of 'image_url' or 'image_path' should be provided.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            playlist_id = args.get("playlist_id") if args else None
            image_url = args.get("image_url") if args else None
            image_path = args.get("image_path") if args else None

            if not playlist_id:
                return "Playlist ID is required."
            if not (image_url or image_path):
                return "Either image URL or image path is required."
            if image_url and image_path:
                return "Provide only one of image URL or image path."

            # Convert image to base64
            if image_url:
                response = requests.get(image_url)
                if response.status_code != 200:
                    return "Error fetching the image from the URL."
                image_base64 = base64.b64encode(response.content).decode("utf-8")

            elif image_path:
                with open(image_path, "rb") as image_file:
                    image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

            # Upload the base64 image
            self.sp.playlist_upload_cover_image(playlist_id, image_base64)
            return "Custom cover image added to the playlist successfully."

        except Exception as e:
            logger.error(f"Error adding custom cover image: {str(e)}")
            return "Error adding custom cover image."

    @playlists
    def user_playlist_unfollow(self, args=None) -> str:
        """
        Unfollows (unsubscribes from) a Spotify playlist.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'playlist_id' (str): ID of the playlist to unfollow.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            logger.info(f"Arguments: {args}")
            playlist_id = args.get("playlist_id") if args else None
            if not playlist_id:
                return "Playlist ID is required."

            self.sp.user_playlist_unfollow(user='me', playlist_id = playlist_id)
            return "Unfollowed the playlist successfully."

        except Exception as e:
            logger.error(f"Error unfollowing playlist: {str(e)}")
            return "Error unfollowing playlist."

    @tracks
    def get_track(self, args=None) -> str:
        """
        Retrieves and formats essential information from a Spotify track.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'track_id' (str): ID of the track to retrieve.

        Returns:
        --------
        str:
            Formatted track information or an error message.
        """
        try:
            track_id = args.get("track_id") if args else None
            if not track_id:
                return "Track ID is required."

            # Fetch track info
            track_info = self.sp.track(track_id)

            # Extract relevant information
            name = track_info.get("name", "Unknown")
            artist_name = track_info["artists"][0].get("name", "Unknown")
            album_name = track_info["album"].get("name", "Unknown")
            release_date = track_info["album"].get("release_date", "Unknown")
            popularity = track_info.get("popularity", "Unknown")
            explicit = "Yes" if track_info.get("explicit", False) else "No"
            track_url = track_info["external_urls"].get("spotify", "No URL available")
            image_url = track_info["album"].get("images", [{}])[0].get("url", "No image available")

            # Format duration
            duration_ms = track_info.get("duration_ms", 0)
            duration_minutes = duration_ms // 60000
            duration_seconds = (duration_ms % 60000) // 1000
            duration = f"{duration_minutes}:{duration_seconds:02}"

            # Format track information
            result_str = (
                f"Track Name: {name}\n"
                f"Artist: {artist_name}\n"
                f"Album: {album_name} - Released: {release_date}\n"
                f"Duration: {duration} (mm:ss)\n"
                f"Popularity: {popularity}\n"
                f"Explicit: {explicit}\n"
                f"Track URL: {track_url}\n"
                f"Image: {image_url}"
            )

            return result_str

        except Exception as e:
            logger.error(f"Error fetching track: {str(e)}")
            return "Error fetching track."

    @tracks
    def get_user_saved_tracks(self, args=None) -> str:
        """
        Retrieves a list of tracks saved by the current Spotify user.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'limit' (int): Number of saved tracks to retrieve.
                - 'offset' (int): Starting point for saved tracks.

        Returns:
        --------
        str:
            A formatted list of saved tracks or an error message.
        """
        try:
            limit = min(max(args.get("limit", 20), 1), 50) if args else 20
            offset = args.get("offset", 0) if args else 0

            # Fetch saved tracks
            saved_tracks = self.sp.current_user_saved_tracks(limit=limit, offset=offset)
            if not saved_tracks or not saved_tracks.get('items'):
                return "No saved tracks found."

            # Format track information
            tracks_info = []
            for item in saved_tracks['items']:
                track = item.get('track')
                if track:
                    track_name = track.get('name', 'Unknown Track')
                    artist_name = track['artists'][0]['name'] if track.get('artists') else 'Unknown Artist'
                    album_name = track['album']['name'] if track.get('album') else 'Unknown Album'
                    album_url = track['album']['external_urls']['spotify'] if track.get('album') and track['album'].get('external_urls') else 'No Album URL'
                    track_url = track['external_urls']['spotify'] if track.get('external_urls') else 'No URL'
                    
                    # Convert duration to mm:ss format
                    duration_ms = track.get('duration_ms', 0)
                    duration_minutes = duration_ms // 60000
                    duration_seconds = (duration_ms % 60000) // 1000
                    duration = f"{duration_minutes}:{duration_seconds:02}"

                    tracks_info.append(
                        f"Track: {track_name}, Artist: {artist_name}, Album: {album_name}, "
                        f"Duration: {duration}, Album URL: {album_url}, Track URL: {track_url}"
                    )

            return '\n'.join(tracks_info)

        except Exception as e:
            logger.error(f"Error fetching saved tracks: {str(e)}")
            return "Error fetching saved tracks."

    @tracks
    def save_track_for_user(self, args=None) -> str:
        """
        Saves a track to the current user's Spotify library.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'track_id' (str or list): ID(s) of the track(s) to save.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            track_id = args.get("track_id") if args else None
            if not track_id:
                return "Track ID is required."

            # Handle both single and multiple track IDs
            track_ids = [track_id] if isinstance(track_id, str) else track_id
            self.sp.current_user_saved_tracks_add(track_ids)
            logger.info(f"Track(s) {track_ids} saved successfully.")
            return "Track saved successfully."

        except Exception as e:
            logger.error(f"Error saving track: {str(e)}")
            return "Error saving track."

    @tracks
    def remove_user_saved_tracks(self, args=None) -> str:
        """
        Removes one or more tracks from the current user's Spotify library.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'track_id' (str or list): ID(s) of the track(s) to remove.

        Returns:
        --------
        str:
            Success or error message.
        """
        try:
            track_id = args.get("track_id") if args else None
            if not track_id:
                return "Track ID is required."

            # Handle both single and multiple track IDs
            track_ids = [track_id] if isinstance(track_id, str) else track_id
            self.sp.current_user_saved_tracks_delete(track_ids)
            logger.info(f"Track(s) {track_ids} removed successfully for the user.")
            return f"{'Track' if len(track_ids) == 1 else 'Tracks'} removed successfully."

        except Exception as e:
            logger.error(f"Error removing track(s): {str(e)}")
            return "Error removing track(s)."

    @tracks
    def check_user_saved_tracks(self, args=None) -> str:
        """
        Checks if the current user has saved specific track(s).

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'track_id' (str or list): ID(s) of the track(s) to check.

        Returns:
        --------
        str:
            Success message indicating whether each track is saved or not.
        """
        try:
            track_id = args.get("track_id") if args else None
            if not track_id:
                return "Track ID is required."

            # Handle both single and multiple track IDs
            track_ids = [track_id] if isinstance(track_id, str) else track_id
            is_saved = self.sp.current_user_saved_tracks_contains(track_ids)

            # Generate summary of saved status
            result = []
            for i, track in enumerate(track_ids):
                status = "saved" if is_saved[i] else "not saved"
                result.append(f"Track {track} is {status}.")
            
            logger.info(f"Checked saved status for tracks: {track_ids}")
            return '\n'.join(result)

        except Exception as e:
            logger.error(f"Error checking saved track(s): {str(e)}")
            return "Error checking saved track(s)."

    @tracks
    def get_track_audio_features(self, args=None) -> str:
        """
        Retrieves audio features of a Spotify track.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'track_id' (str): ID of the track to retrieve features for.

        Returns:
        --------
        str:
            Formatted audio features information or an error message.
        """
        try:
            track_id = args.get("track_id") if args else None
            if not track_id:
                return "Track ID is required."

            # Fetch audio features
            features = self.sp.audio_features(track_id)[0]
            if not features:
                return "No audio features found for the track."

            # Extract relevant features
            acousticness = f"{features.get('acousticness', 'Unknown'):.3f}"
            danceability = f"{features.get('danceability', 'Unknown'):.3f}"
            energy = f"{features.get('energy', 'Unknown'):.3f}"
            instrumentalness = f"{features.get('instrumentalness', 'Unknown'):.3f}"
            liveness = f"{features.get('liveness', 'Unknown'):.3f}"
            loudness = f"{features.get('loudness', 'Unknown'):.1f} dB"
            speechiness = f"{features.get('speechiness', 'Unknown'):.3f}"
            tempo = f"{features.get('tempo', 'Unknown'):.1f} BPM"
            valence = f"{features.get('valence', 'Unknown'):.3f}"
            
            # Add mode and key
            mode = "Major" if features.get('mode') == 1 else "Minor"
            key = features.get("key", "Unknown")

            # Format audio features information
            result_str = (
                f"Acousticness: {acousticness}\n"
                f"Danceability: {danceability}\n"
                f"Energy: {energy}\n"
                f"Instrumentalness: {instrumentalness}\n"
                f"Liveness: {liveness}\n"
                f"Loudness: {loudness}\n"
                f"Speechiness: {speechiness}\n"
                f"Tempo: {tempo}\n"
                f"Valence: {valence}\n"
                f"Key: {key}\n"
                f"Mode: {mode}"
            )

            return result_str

        except Exception as e:
            logger.error(f"Error fetching audio features: {str(e)}")
            return "Error fetching audio features."

    @albums
    def get_album(self, args=None) -> str:
        """
        Retrieves and formats essential information from a Spotify album.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'album_id' (str): ID of the album to retrieve.

        Returns:
        --------
        str:
            Formatted album information or an error message.
        """
        try:
            album_id = args.get("album_id") if args else None
            if not album_id:
                return "Album ID is required."

            # Fetch album info
            album_info = self.sp.album(album_id)

            # Extract relevant information
            name = album_info.get("name", "Unknown")
            artist_name = album_info["artists"][0].get("name", "Unknown")
            release_date = album_info.get("release_date", "Unknown")
            total_tracks = album_info.get("total_tracks", "Unknown")
            album_type = album_info.get("album_type", "Unknown")
            album_url = album_info["external_urls"].get("spotify", "No URL available")
            image_url = album_info.get("images", [{}])[0].get("url", "No image available")
            genres = ', '.join(album_info.get("genres", []))
            label = album_info.get("label", "Unknown")

            # Format album information
            result_str = (
                f"Album Name: {name}\n"
                f"Artist: {artist_name}\n"
                f"Release Date: {release_date}\n"
                f"Total Tracks: {total_tracks}\n"
                f"Album Type: {album_type}\n"
                f"Genres: {genres or 'No genre information'}\n"
                f"Label: {label}\n"
                f"Album URL: {album_url}\n"
                f"Image: {image_url}"
            )

            return result_str

        except Exception as e:
            logger.error(f"Error fetching album: {str(e)}")
            return "Error fetching album."

    @albums
    def get_album_tracks(self, args=None) -> str:
        """
        Retrieves tracks from a Spotify album.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'album_id' (str): ID of the album to retrieve tracks from.
                - 'limit' (int, optional): Number of tracks to retrieve.
                - 'offset' (int, optional): Starting point for tracks.

        Returns:
        --------
        str:
            A formatted list of album tracks or an error message.
        """
        try:
            album_id = args.get("album_id") if args else None
            limit = args.get("limit", 20) if args else 20
            offset = args.get("offset", 0) if args else 0

            if not album_id:
                return "Album ID is required."

            # Fetch album tracks
            tracks = self.sp.album_tracks(album_id, limit=limit, offset=offset)
            if not tracks or not tracks.get('items'):
                return "No tracks found in the album."

            # Format detailed track information
            tracks_info = []
            for track in tracks['items']:
                track_name = track.get('name', 'Unknown Track')
                artist_name = track['artists'][0].get('name', 'Unknown Artist') if track.get('artists') else 'Unknown Artist'
                duration_ms = track.get('duration_ms', 0)
                duration_minutes = duration_ms // 60000
                duration_seconds = (duration_ms % 60000) // 1000
                duration = f"{duration_minutes}:{duration_seconds:02}"
                explicit = "Yes" if track.get("explicit", False) else "No"
                track_url = track['external_urls'].get('spotify', 'No URL')

                # Append formatted track info
                tracks_info.append(
                    f"Track: {track_name}\n"
                    f"Artist: {artist_name}\n"
                    f"Duration: {duration}\n"
                    f"Explicit: {explicit}\n"
                    f"URL: {track_url}\n"
                )

            return '\n\n'.join(tracks_info)

        except Exception as e:
            logger.error(f"Error fetching album tracks: {str(e)}")
            return "Error fetching album tracks."

    @users
    def get_user_top_items(self, args=None) -> str:
        """
        Retrieves the current user's top artists or tracks.

        Parameters:
        -----------
        args : dict, optional
            Dictionary containing:
                - 'type' (str): Type of top items to retrieve (artists or tracks).
                - 'limit' (int, optional): Number of items to retrieve.
                - 'time_range' (str, optional): Time range for top items (short_term, medium_term, long_term).

        Returns:
        --------
        str:
            A formatted list of top items or an error message.
        """
        try:
            top_type = args.get("type") if args else None
            limit = args.get("limit", 10) if args else 10
            time_range = args.get("time_range", "medium_term") if args else "medium_term"

            if not top_type:
                return "Type of top items is required."

            # Fetch top items
            if top_type == "artists":
                top_items = self.sp.current_user_top_artists(limit=limit, time_range=time_range)
            elif top_type == "tracks":
                top_items = self.sp.current_user_top_tracks(limit=limit, time_range=time_range)
            else:
                return "Invalid type of top items. Choose 'artists' or 'tracks'."

            if not top_items or not top_items.get('items'):
                return f"No top {top_type} found for the user."

            # Format top items information
            top_items_info = []
            for i, item in enumerate(top_items['items']):
                name = item.get('name', 'Unknown')
                url = item.get('external_urls', {}).get('spotify', 'No URL available')
                top_items_info.append(f"{i + 1}. {name} - {url}")

            return '\n'.join(top_items_info)

        except Exception as e:
            logger.error(f"Error fetching top items: {str(e)}")
            return "Error fetching top items."

    @users
    def get_current_user_profile(self, args=None) -> str:
        """
        Retrieves and formats essential information about the current Spotify user.

        Returns:
        --------
        str:
            Formatted user profile information or an error message.
        """
        try:
            user_info = self.sp.me()
            if not user_info:
                return "No user information found."

            # Extract relevant information
            display_name = user_info.get("display_name", "Unknown")
            email = user_info.get("email", "Unknown")
            followers = user_info.get("followers", {}).get("total", 0)
            country = user_info.get("country", "Unknown")
            user_url = user_info.get("external_urls", {}).get("spotify", "No URL available")
            
            # Check if images exist
            image_url = user_info.get("images", [{}])[0].get("url", "No image available") if user_info.get("images") else "No image available"

            # Format user profile information
            result_str = (
                f"Display Name: {display_name}\n"
                f"Email: {email}\n"
                f"Followers: {followers}\n"
                f"Country: {country}\n"
                f"User URL: {user_url}\n"
                f"Image: {image_url}"
            )

            return result_str

        except Exception as e:
            logger.error(f"Error fetching user profile: {str(e)}")
            return "Error fetching user profile."

