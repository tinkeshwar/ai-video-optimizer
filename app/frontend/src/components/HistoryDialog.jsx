import React from 'react';
import { Flex, Button, Text, Box, Badge } from '@radix-ui/themes';
import { Cross2Icon } from '@radix-ui/react-icons';
import { relativeTime } from '../helpers';

const STATUS_COLORS = {
  pending: 'yellow',
  confirmed: 'blue',
  ready: 'indigo',
  optimized: 'green',
  accepted: 'grass',
  replaced: 'grass',
  rejected: 'orange',
  skipped: 'gray',
  failed: 'red',
  're-confirmed': 'blue',
};

function HistoryDialog({ open, filename, history, onClose }) {
  if (!open) return null;
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
          minWidth: 360, maxWidth: 500, maxHeight: '70vh',
          overflow: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Flex justify="between" align="center" mb="3" gap="2">
          <Text size="3" weight="bold" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 }}>📜 History — {filename}</Text>
          <Button size="1" variant="ghost" onClick={onClose} style={{ flexShrink: 0 }}><Cross2Icon /></Button>
        </Flex>
        {(!history || history.length === 0) ? (
          <Text size="2" color="gray">No history available.</Text>
        ) : (
          <Flex direction="column" gap="2">
            {history.map((h, i) => (
              <Flex key={i} align="center" gap="3" p="2" style={{ borderLeft: '2px solid var(--history-border)', paddingLeft: 12 }}>
                <Badge size="1" color={STATUS_COLORS[h.status] || 'gray'}>{h.status}</Badge>
                <Text size="1" color="gray">{relativeTime(h.created_at)}</Text>
                {h.comment && <Text size="1" style={{ wordBreak: 'break-word', minWidth: 0 }}>— {h.comment}</Text>}
              </Flex>
            ))}
          </Flex>
        )}
      </Box>
    </div>
  );
}

export default HistoryDialog;
