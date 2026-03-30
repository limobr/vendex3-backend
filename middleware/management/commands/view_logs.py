# backend/middleware/management/commands/view_logs.py
from django.core.management.base import BaseCommand
import os
from pathlib import Path
from django.conf import settings

class Command(BaseCommand):
    help = 'View request logs with various filters'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='requests',
            choices=['requests', 'performance', 'analytics', 'all'],
            help='Type of logs to view'
        )
        parser.add_argument(
            '--lines',
            type=int,
            default=50,
            help='Number of lines to show'
        )
        parser.add_argument(
            '--filter',
            type=str,
            help='Filter logs by string'
        )
    
    def handle(self, *args, **options):
        log_type = options['type']
        lines = options['lines']
        filter_str = options['filter']
        
        log_files = {
            'requests': 'requests.log',
            'performance': 'performance.log',
            'analytics': 'analytics.log',
            'all': ['requests.log', 'performance.log', 'analytics.log']
        }
        
        log_dir = os.path.join(settings.BASE_DIR, 'logs')
        
        if not os.path.exists(log_dir):
            self.stdout.write(self.style.ERROR('Logs directory does not exist'))
            return
        
        if log_type == 'all':
            for log_file in log_files['all']:
                self.display_log_file(log_dir, log_file, lines, filter_str)
        else:
            log_file = log_files[log_type]
            self.display_log_file(log_dir, log_file, lines, filter_str)
    
    def display_log_file(self, log_dir, log_file, lines, filter_str):
        file_path = os.path.join(log_dir, log_file)
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.WARNING(f'Log file {log_file} does not exist'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'--- {log_file} ---'))
        
        with open(file_path, 'r') as f:
            file_lines = f.readlines()
        
        if filter_str:
            file_lines = [line for line in file_lines if filter_str.lower() in line.lower()]
        
        # Show last N lines
        for line in file_lines[-lines:]:
            self.stdout.write(line.strip())