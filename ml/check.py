"""Read-only model setup check: python -m ml.check [--artifact-dir PATH]."""
import argparse
import sys

from ml.service import DEFAULT_ARTIFACT_DIR, ModelService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifact-dir', default=DEFAULT_ARTIFACT_DIR)
    args = parser.parse_args()
    model = ModelService(args.artifact_dir)
    status = model.status()
    print('Python:', sys.executable)
    if not status['available']:
        print('Model unavailable:', status['reason'])
        return 1
    # In-memory fixture only: no assessment, identity, or database is created.
    sample = {'age': 19, 'daily_time': '1to3', 'passive': 'often', 'active': 'rarely',
              'night': 'sometimes', 'cyberbullying': 'never', 'regular_count': '2'}
    result = model.predict(sample)
    if result['estimate'] is None:
        print('Model loaded but prediction failed:', result['reason'])
        return 1
    print('Model:', status['version'])
    print('Runtime:', status['runtime'])
    print('Integrity, prediction and explanation:', 'OK' if result['explanation'] else 'prediction OK; explanation unavailable')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
