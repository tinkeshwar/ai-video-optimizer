import React, { useState, useEffect } from 'react';
import { Flex, Button, Text, Box } from '@radix-ui/themes';
import { Cross2Icon } from '@radix-ui/react-icons';

function StreamSelectDialog({ open, filename, audioStreams, subtitleStreams, onConfirm, onClose }) {
  const [selectedAudio, setSelectedAudio] = useState(null);
  const [selectedSubtitle, setSelectedSubtitle] = useState(null);

  const prevOpen = React.useRef(false);
  useEffect(() => {
    if (open && !prevOpen.current) {
      const audio = audioStreams || [];
      setSelectedAudio(audio.length === 1 ? audio[0].index : null);
      setSelectedSubtitle(null);
    }
    prevOpen.current = open;
  }, [open, audioStreams]);

  if (!open) return null;

  const audio = audioStreams || [];
  const subs = subtitleStreams || [];

  const handleConfirm = () => {
    const audioObj = audio.find(a => a.index === selectedAudio);
    const subObj = subs.find(s => s.index === selectedSubtitle) || null;
    onConfirm(audioObj, subObj);
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9998,
        background: 'var(--overlay-bg)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onClose}
    >
      <Box
        p="5"
        style={{
          background: 'var(--dialog-bg)', borderRadius: 12,
          boxShadow: 'var(--dialog-shadow)',
          width: 560, maxWidth: '90vw', maxHeight: '85vh', overflow: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Flex justify="between" align="center" mb="3">
          <Text size="3" weight="bold">🎧 Select Streams — {filename}</Text>
          <Button size="1" variant="ghost" onClick={onClose}><Cross2Icon /></Button>
        </Flex>

        <Box mb="3">
          <Text size="2" weight="bold" mb="2" style={{ display: 'block' }}>Audio Stream (required)</Text>
          {audio.map((a) => (
            <label key={a.index} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', cursor: 'pointer' }}>
              <input
                type="radio" name="audio" checked={selectedAudio === a.index}
                onChange={() => setSelectedAudio(a.index)}
              />
              <Text size="1">
                #{a.index} — {a.codec_name} · {a.channels}ch{a.channel_layout ? ` (${a.channel_layout})` : ''} · {a.language || 'und'}
                {a.bit_rate ? ` · ${(Number(a.bit_rate) / 1000).toFixed(0)}kbps` : ''}
              </Text>
            </label>
          ))}
        </Box>

        <Box mb="3">
          <Text size="2" weight="bold" mb="2" style={{ display: 'block' }}>Subtitle Stream (optional)</Text>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', cursor: 'pointer' }}>
            <input
              type="radio" name="subtitle" checked={selectedSubtitle === null}
              onChange={() => setSelectedSubtitle(null)}
            />
            <Text size="1" color="gray">None (remove all subtitles)</Text>
          </label>
          {subs.map((s) => (
            <label key={s.index} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', cursor: 'pointer' }}>
              <input
                type="radio" name="subtitle" checked={selectedSubtitle === s.index}
                onChange={() => setSelectedSubtitle(s.index)}
              />
              <Text size="1">#{s.index} — {s.codec_name} · {s.language || 'und'}</Text>
            </label>
          ))}
          {subs.length === 0 && (
            <Text size="1" color="gray" style={{ paddingLeft: 24 }}>No subtitle streams found</Text>
          )}
        </Box>

        <Flex gap="2" mt="3" justify="end">
          <Button size="2" variant="soft" color="gray" onClick={onClose}>Cancel</Button>
          <Button size="2" color="green" disabled={selectedAudio === null} onClick={handleConfirm}>
            Confirm
          </Button>
        </Flex>
      </Box>
    </div>
  );
}

export default StreamSelectDialog;
