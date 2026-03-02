# VHS documentation
#
# Output:
#   Output <path>.gif               Create a GIF output at the given <path>
#   Output <path>.mp4               Create an MP4 output at the given <path>
#   Output <path>.webm              Create a WebM output at the given <path>
#
Output elefante_benchmark.gif

Set FontSize 16
Set FontFamily "JetBrains Mono"
Set Width 1200
Set Height 800
Set TypingSpeed 0.1s
Set Theme "TokyoNight"

# Navigation
Type "source .venv/bin/activate"
Enter
Sleep 1s

# Clear screen before benchmark
Type "clear"
Enter

# Run the benchmark
Type "PYTHONPATH=. python scripts/run_benchmark.py"
Enter
Sleep 25s

# Wait for users to read the final table
Sleep 5s
