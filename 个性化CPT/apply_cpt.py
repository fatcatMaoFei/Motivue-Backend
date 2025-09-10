#!/usr/bin/env python3
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from readiness.personalization_simple import load_personalized_cpt

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'personalized_emission_cpt_standard_user.json')
    load_personalized_cpt(path)

if __name__ == '__main__':
    main()

