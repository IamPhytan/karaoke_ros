# Current state of the player, published continuously on /karaoke/state
string song          # name of the loaded file
string title
string artist
bool playing
float32 position     # seconds since the beginning
float32 duration     # seconds
int32 line_index     # -1 before the first line
int32 line_count
string current_line
string current_word
string next_line