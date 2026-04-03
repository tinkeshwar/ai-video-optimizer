export const byteToHuman = (bytes) => {
  if (!bytes) return 'NA';
  const gb = bytes / 1e9;
  const mb = bytes / 1e6;
  return gb >= 1 ? `${gb.toFixed(2)} GB` : `${mb.toFixed(2)} MB`;
};

export const formatDuration = (seconds) => {
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

export const relativeTime = (dateStr) => {
  if (!dateStr) return '';
  const now = new Date();
  const date = new Date(dateStr + 'Z');
  const diff = Math.floor((now - date) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return date.toLocaleDateString();
};

export const compressionPercent = (original, compressed) => {
  if (!original || !compressed || original <= 0) return 'NA';
  return `${(((original - compressed) / original) * 100).toFixed(1)}%`;
};

export const runtimeFromProbe = (ffprobe) => {
  try {
    const data = JSON.parse(ffprobe);
    return formatDuration(parseFloat(data.duration));
  } catch {
    return 'NA';
  }
};

export const progressFromProbe = (ffprobe, ffmpegOut) => {
  try {
    const data = JSON.parse(ffprobe);
    const duration = parseFloat(data.duration);
    const timeMatch = ffmpegOut.match(/time=(\d+):(\d+):(\d+\.\d+)/);
    const speedMatch = ffmpegOut.match(/speed=([\d.]+)x/);
    const bitrateMatch = ffmpegOut.match(/bitrate=\s*([\d.]+)kbits\/s/);
    if (!timeMatch || !speedMatch) return { percent: 0, eta: 'NA', size: 'NA', processed: 'NA' };
    const [, hh, mm, ss] = timeMatch;
    const cur = (+hh) * 3600 + (+mm) * 60 + (+ss);
    const speed = parseFloat(speedMatch[1]);
    const bitrate = bitrateMatch ? parseFloat(bitrateMatch[1]) * 1000 : null;
    const remaining = (duration - cur) / speed;
    const estSize = bitrate ? ((duration * bitrate) / 8) : 0;
    return {
      percent: Number(((cur / duration) * 100).toFixed(2)),
      eta: formatDuration(remaining),
      size: estSize ? byteToHuman(estSize) : 'NA',
      processed: formatDuration(cur),
    };
  } catch {
    return { percent: 0, eta: 'NA', size: 'NA', processed: 'NA' };
  }
};
