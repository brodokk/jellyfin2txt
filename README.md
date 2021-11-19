# jellyfin2txt

Simple API for NeosVr for getting movies and series from a jellyfin server.

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

Each endpoint response is sended without a new line at the end. Each entry
is separated by `;`. But beware the first entry is not a proper entry. Its
the pagging system information who is not implemented yet in the folowing
format: `start_index,count`.

* `/movies/` Return the list of movies where an item is in the format `name,img_url,dl_url,stream_url,trailer_url,external_url`
* `/series/` Return the list of series where an item is in the format `name,img_url,serie_id,external_url`
* `/series/<serie_id>` Return the list of seasons of the serie where an item is in the format `name,img_url,season_id`
* `/series/<serie_id>/<sesaon_id>` Return the list of episode of the season of the serie where an item is in the format
  `name,img_url,dl_url,stream_url`

For authentification the API search in the POST data as a json with the key `auth_key`. The value is
directly the key.

Example with curl:

```
curl -d '{"auth_key":"xxxxxxxxxxxx"}' -H "Content-Type: application/json" -X POST https://jellyfin2text.example.com
```
 
# TODO

* [ ] Implement paging system
