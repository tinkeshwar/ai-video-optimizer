import React, { createContext, useContext, useState, useCallback } from 'react';
import { Flex, Text } from '@radix-ui/themes';
import { CheckCircledIcon, CrossCircledIcon, InfoCircledIcon } from '@radix-ui/react-icons';

const ToastContext = createContext();

const ICONS = {
  success: <CheckCircledIcon />,
  error: <CrossCircledIcon />,
  info: <InfoCircledIcon />,
};

const COLORS = {
  success: { bg: '#dcfce7', border: '#86efac', text: '#166534' },
  error: { bg: '#fee2e2', border: '#fca5a5', text: '#991b1b' },
  info: { bg: '#dbeafe', border: '#93c5fd', text: '#1e40af' },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = 'info') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3000);
  }, []);

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      <div style={{ position: 'fixed', bottom: 16, right: 16, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map((t) => (
          <Flex
            key={t.id}
            align="center"
            gap="2"
            p="3"
            style={{
              background: COLORS[t.type].bg,
              border: `1px solid ${COLORS[t.type].border}`,
              borderRadius: 8,
              color: COLORS[t.type].text,
              boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              animation: 'slideIn 0.2s ease-out',
              minWidth: 250,
            }}
          >
            {ICONS[t.type]}
            <Text size="2">{t.message}</Text>
          </Flex>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
