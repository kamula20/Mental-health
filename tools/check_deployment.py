"""Read-only HTTP readiness check for an operator-owned deployment."""
import argparse
import json
import urllib.request


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',default='http://127.0.0.1:5000')
    parser.add_argument('--require-production',action='store_true')
    args=parser.parse_args()
    root=args.base_url.rstrip('/')
    if args.require_production and not root.startswith('https://'):
        raise ValueError('Production checks require an HTTPS URL.')
    for route in ('/healthz','/readyz','/api/session'):
        with urllib.request.urlopen(root+route,timeout=15) as response:
            value=json.load(response)
            if route=='/api/session' and args.require_production and value.get('demo') is not False:
                raise ValueError('Public demo access is still enabled.')
            print(route,response.status)
    print('Deployment responds and model/database readiness checks pass.')


if __name__=='__main__':
    main()
