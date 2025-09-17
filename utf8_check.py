import sys, locale
print('stdout.encoding =', getattr(sys.stdout, 'encoding', None))
print('stderr.encoding =', getattr(sys.stderr, 'encoding', None))
print('preferredencoding =', locale.getpreferredencoding(False))
print('env PYTHONIOENCODING =', __import__('os').environ.get('PYTHONIOENCODING'))
print('Тест кириллицы: Привет, мир! 你好 こんにちは')