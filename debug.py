from pytubefix import YouTube


yt = YouTube("https://www.youtube.com/live/LJT7TCcvg_k")
yt.streams.filter(progressive=True, file_extension="mp4")

print(yt.title)
print(yt.thumbnail_url)
print(yt.length)
print(yt.views)
resolutions = [stream.resolution for stream in yt.streams.filter(file_extension="mp4")]
print(resolutions)