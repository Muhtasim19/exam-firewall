#!/bin/bash
# Sync files from exam-firewall to exam-firewall/exam-firewall
cp ~/exam-firewall/templates/*.html ~/exam-firewall/exam-firewall/templates/
cp ~/exam-firewall/static/* ~/exam-firewall/exam-firewall/static/
cp ~/exam-firewall/*.py ~/exam-firewall/exam-firewall/
sudo systemctl restart exam-dashboard exam-analytics
echo "✅ Sync complete!"
