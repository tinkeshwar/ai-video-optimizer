import React from 'react';
import { Flex, Button, Text, Box } from '@radix-ui/themes';

function ConfirmDialog({ open, message, onConfirm, onCancel }) {
  if (!open) return null;
  return (
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 9998,
        background: 'var(--overlay-bg)', display: 'flex',
        alignItems: 'center', justifyContent: 'center',
      }}
      onClick={onCancel}
    >
      <Box
        p="5"
        style={{
          background: 'var(--dialog-bg)', borderRadius: 12,
          boxShadow: 'var(--dialog-shadow)',
          minWidth: 320, maxWidth: 420,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <Text size="3" weight="medium">{message}</Text>
        <Flex gap="2" mt="4" justify="end">
          <Button size="2" variant="soft" color="gray" onClick={onCancel}>Cancel</Button>
          <Button size="2" color="red" onClick={onConfirm}>Confirm</Button>
        </Flex>
      </Box>
    </div>
  );
}

export default ConfirmDialog;
