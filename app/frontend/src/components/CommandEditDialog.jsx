import React, { useState, useEffect } from 'react';
import { Flex, Button, Text, Box, TextArea } from '@radix-ui/themes';
import { Cross2Icon } from '@radix-ui/react-icons';
import { byteToHuman, formatDuration } from '../helpers';

function parseMeta(ffprobeData) {
  try {
    const d = typeof ffprobeData === 'string' ? JSON.parse(ffprobeData) : ffprobeData;
    return {
      format: d.format_long_name || d.format_name || 'Unknown',
      duration: d.duration ? formatDuration(parseFloat(d.duration)) : 'NA',
      size: d.size ? byteToHuman(Number(d.size)) : 'NA',
      bitrate: d.bit_rate ? `${(Number(d.bit_rate) / 1000).toFixed(0)} kbps` : 'NA',
      streams: d.nb_streams ?? 'NA',
    };
  } catch {
    return null;
  }
}

const MetaRow = ({ label, value }) => (
  <Flex justify="between" py="1" style={{ borderBottom: '1px solid var(--meta-row-border)' }}>
    <Text size="1" color="gray">{label}</Text>
    <Text size="1" weight="medium">{value}</Text>
  </Flex>
);

function CommandEditDialog({ open, filename, command, ffprobeData, onSave, onClose }) {
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) {
      setValue(command || 'ffmpeg -i input.mp4 ');
      setError('');
    }
  }, [open, command]);

  if (!open) return null;

  const meta = parseMeta(ffprobeData);

  const handleSave = () => {
    const trimmed = value.trim();
    if (!trimmed.startsWith('ffmpeg')) {
      setError('Command must start with ffmpeg');
      return;
    }
    onSave(trimmed);
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
          width: 600, maxWidth: '90vw', maxHeight: '85vh', overflow: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Flex justify="between" align="center" mb="3">
          <Text size="3" weight="bold">✏️ Edit Command — {filename}</Text>
          <Button size="1" variant="ghost" onClick={onClose}><Cross2Icon /></Button>
        </Flex>

        {meta && (
          <Box mb="3" p="3" style={{ background: 'var(--meta-bg)', borderRadius: 8, border: '1px solid var(--meta-border)' }}>
            <Text size="1" weight="bold" color="gray" mb="2" style={{ display: 'block' }}>📋 Video Metadata</Text>
            <MetaRow label="Format" value={meta.format} />
            <MetaRow label="Duration" value={meta.duration} />
            <MetaRow label="Size" value={meta.size} />
            <MetaRow label="Bitrate" value={meta.bitrate} />
            <MetaRow label="Streams" value={meta.streams} />
          </Box>
        )}

        <Text size="1" color="gray" mb="2" style={{ display: 'block' }}>
          Use input.mp4 as input and output.mp4 as output. The processor will replace these with actual paths.
        </Text>
        <TextArea
          size="2"
          rows={6}
          value={value}
          onChange={(e) => { setValue(e.target.value); setError(''); }}
          style={{ fontFamily: 'monospace', fontSize: 12, width: '100%' }}
        />
        {error && <Text size="1" color="red" mt="1">{error}</Text>}
        <Flex gap="2" mt="3" justify="end">
          <Button size="2" variant="soft" color="gray" onClick={onClose}>Cancel</Button>
          <Button size="2" color="blue" onClick={handleSave}>Save & Queue</Button>
        </Flex>
      </Box>
    </div>
  );
}

export default CommandEditDialog;
