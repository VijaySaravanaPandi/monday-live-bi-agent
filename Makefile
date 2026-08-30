.PHONY: install test run test-phase1 test-phase2 test-phase3 test-phase4 test-phase5

install:
	pip install -r requirements.txt

test: test-phase1 test-phase2 test-phase3 test-phase4 test-phase5

test-phase1:
	python main.py

test-phase2:
	python test_phase2.py

test-phase3:
	python test_phase3.py

test-phase4:
	python test_phase4.py

test-phase5:
	python test_phase5.py

run:
	uvicorn src.api:app --reload --port 8000

zip:
	python package_submission.py
