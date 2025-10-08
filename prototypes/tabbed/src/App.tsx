import React from 'react';
import { DocReview } from './pages/DocReview';

export const App: React.FC = () => {
  return (
    <div style={{height:'100vh'}}>
      {/* Expect bundle and verify assets to be available under server root or vite public */}
      <DocReview bundleUrl="/ui/blocks_full.json" verifyDir="/05_table_extractor/verify" />
    </div>
  );
};
