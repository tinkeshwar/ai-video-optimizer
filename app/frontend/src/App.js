import React, { useState, useEffect } from 'react';
import FileList from './components/FileList';
import { ToastProvider } from './components/Toast';
import { Theme, Button } from '@radix-ui/themes';
import { SunIcon, MoonIcon } from '@radix-ui/react-icons';

function App() {
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved) return saved === 'dark';
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
  });

  useEffect(() => {
    localStorage.setItem('theme', dark ? 'dark' : 'light');
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  return (
    <Theme appearance={dark ? 'dark' : 'light'} accentColor="indigo" radius="medium">
      <ToastProvider>
        <div style={{ position: 'fixed', top: 12, right: 16, zIndex: 200 }}>
          <Button size="1" variant="ghost" onClick={() => setDark((d) => !d)}>
            {dark ? <SunIcon /> : <MoonIcon />}
          </Button>
        </div>
        <FileList />
      </ToastProvider>
    </Theme>
  );
}

export default App;
