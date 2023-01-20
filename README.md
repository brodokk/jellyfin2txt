# jellyfin2txt

Simple API for NeosVr for getting movies and series from a jellyfin server.

Note: Like Jellyfin the developers of the server and the clients are not
responsible of what **YOU** are doing with this tools.

The issues for the repository handle both this server and the NeosVR client.

## Installation

Requirements:

* Python 3.7

## Usage

For launch the server your just need to run the scrip `app.py`:

```
usage: app.py [-h] [--port PORT] [--debug]

optional arguments:
  -h, --help   show this help message and exit
  --port PORT  Port to use, default 5000
  --debug      Make the server verbose
```

Each endpoint of the API is currently lock behind a key you can manage with
the little script `key.py`.

```
usage: key.py [-h] [genkey ...] [revokekey ...] [listkeys ...]

script 1.0

positional arguments:
  genkey      Generate a new key
  revokekey   Revoke a key. The format should be key=<id>
  listkeys    List all the key available

optional arguments:
  -h, --help  show this help message and exit
```

The API have 4 endpoints:

Each endpoint response is sended without a new line at the end. Each entry
is separated by `;`. But beware the first entry is not a proper entry for the
endpoints `movies` and `series`. Its the pagging system information in the
folowing format: `start_index,total_record_count`.

* `/movies/` Return the list of movies where an item is in the format `name,img_url,dl_url,stream_url,trailer_url,external_url`. This endpoint also support two url parameters:
	* `StartIndex` that you can use for start from a special index. Default to 0.
	* `Limit` that you can use for set a limit of the number of item to get from the server. Default to 100.
        * `ThumbFillHeight` that you can use for change the height of the thumbnail. Default to 320.
	* `ThumbFillWidth` that you can use for change the width of the thumbnail. Default to 213.
	* `ThumbQuality` that you can use for change the quality of the thumbnail, in percent. Default to 96.
* `/series/` Return the list of series where an item is in the format `name,img_url,serie_id,external_url`. This endpoint also support two url parameters:
	* `StartIndex` that you can use for start from a special index. Default to 0.
	* `Limit` that you can use for set a limit of the number of item to get from the server. Default to 100.
        * `ThumbFillHeight` that you can use for change the height of the thumbnail. Default to 320.
	* `ThumbFillWidth` that you can use for change the width of the thumbnail. Default to 213.
	* `ThumbQuality` that you can use for change the quality of the thumbnail, in percent. Default to 96.
* `/series/<serie_id>` Return the list of seasons of the serie where an item is in the format `name,img_url,season_id`
* `/series/<serie_id>/<sesaon_id>` Return the list of episode of the season of the serie where an item is in the format
  `name,img_url,dl_url,stream_url`
* `/subtitles/<media_id>` Return the list of subtitles available for a media where media can either be a movie or an episode.
* `/subtitles/<media_id>/<subtitle_name>` Return the subtitle url available on the proxy.
* `/subtitles/<media_id>/<subtitle_name>/extract` Extract the subtitle from the server. This process can be very long if the subtitle is burned in the media. See `Extracting hardcoded subtitles`.
* `/subtiles/<media_id>/<subtitle_name>/extract/status` Return the status of the extraction process in the format `srt_name,status,item_id,item_name,error_message,created_at,updated_at` where `created_at` and `updated_at` are in milliseconds.
* `/subtiles/<media_id>/discover` Return the subtitles availables based on the language set in the configuration file.
* `/subtiles/<media_id>/all` Return all the subtitles available on the proxy.
* `/extract_status` Return the list of all the status of the extraction processes in the format `srt_name,status,item_id,item_name,error_message,created_at,updated_at` where `created_at` and `updated_at` are in milliseconds. Each task is separated by the `\n`.

For authentification the API search in the POST data as a json with the key `auth_key`. The value is
directly the key.

Example with curl:

```
curl -d '{"auth_key":"xxxxxxxxxxxx"}' -H "Content-Type: application/json" -X POST https://jellyfin2text.example.com
```

## NeosVr clients

A public folder is available for a basic NeosVr client called `JellyfinClient Beta`:
neosrec:///G-The-french-microwave/R-cb7e384b-3879-4395-be1f-ea4a74c09705

### Configuration

The beta version 0.3 have a key where you will need to put the differents
infomation in a slot called `DynVar` just under the root of the of the Jellyfin client:
- `Client/BaseUrl` is the url of the server you want to use as a proxy
- `Client/AuthKey` is the auth key generated from the `key.py` utility needed
  to access to the server.

### Subtitles

This proxy is capabale to serve the following subtitles format:

- `subrip` directly
- `ass`, `move_text` extracted from jellyfin and converted in `srt`
- `PGSSUB` extracted from the movie via OCR and converted in `srt`

#### Extracting hardcoded subtitles

You need to have installed on your system the binary `mkvmerge` available in `MKVToolNix`.
You also need to have `tesseract-ocr` and the tessdata `best`. (For pgsrip)

```
$ git clone https://github.com/tesseract-ocr/tessdata_best.git
export TESSDATA_PREFIX=~/tessdata_best
```

###### PGSUB

Subtitles in this format are using the external module https://github.com/ratoaq2/pgsrip.
If you want to be able to extract file in this format you free RAM **must** be big enough
for have the movie fit inside. Example if you movie is 2GB you need more than 2GB of RAM
available.

### Know issues

- The stream url didnt work yet probably because of this issue: https://github.com/Neos-Metaverse/NeosPublic/issues/2812
- The download url didnt work because Neos dont reconize the file extension

For still being able to see the file of your choice you will need to copy the
download url and open it into your navigator before importing in Neos. Its
better to use the Neos cloud as a storage for streame your file. There is an
option in a context menu to copy the url. If you want to save the cassette you
will need to remove the InventoryLink using the option on the context menu.
Keep in mind the option to copy the link can break at any time.
