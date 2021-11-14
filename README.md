# jellyfin2txt

Simple API for NeosVr for getting movies and series from a jellyfin server.

You can find a NeosVR client here: <not release yet> and a jellyfin2text server is
running at: https://jellyfin2txt.neos.spacealicorn.network

The issues for the repository handle both this server and the NeosVR client.

## Installation

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

* `/movies/` Return the list of movies in the format `start_index,count;name,img_url,dl_url,stream_url,trailer_url,external_url`
* `/series/` Return the list of series in the format `start_index,count;name,img_url,serie_id,external_url`
* `/series/<serie_id>` Return the list of seasons of the serie in the format `start_index,count;name,img_url,season_id`
* `/series/<serie_id>/<sesaon_id>` Return the list of episode of the season of the serie in the format
  `start_index,count;name,img_url,dl_url,stream_url`

For authentification the API search in the POST data as a json with the key `auth_key`. The value is
directly the key.
 
# TODO

* [ ] Implement paging system
