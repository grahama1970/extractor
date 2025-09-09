import './globals.css';

export const metadata = {
  title: 'Gold Annotator 2',
  description: 'Minimal PDF viewer spike'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: 'system-ui, sans-serif' }}>{children}</body>
    </html>
  );
}
