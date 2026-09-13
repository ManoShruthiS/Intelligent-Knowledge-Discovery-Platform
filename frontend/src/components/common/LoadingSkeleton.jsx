import React from 'react';


const shimmerKeyframes = `
@keyframes shimmer {
  0% { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
.loading-skeleton {
  background: linear-gradient(90deg, #e0e0e0 25%, #d0d0d0 50%, #e0e0e0 75%);
  background-size: 800px 100%;
  animation: shimmer 1.5s infinite ease-in-out;
  border-radius: 6px;
}
`;


function injectStyles() {
  if (typeof document !== 'undefined' && !document.getElementById('loading-skeleton-styles')) {
    const style = document.createElement('style');
    style.id = 'loading-skeleton-styles';
    style.textContent = shimmerKeyframes;
    document.head.appendChild(style);
  }
}

injectStyles();


function LoadingSkeleton({ width = '100%', height = '1rem', count = 1, style = {} }) {
  return (
    <>
      {Array.from({ length: count }, (_, i) => (
        <div
          key={i}
          className="loading-skeleton"
          style={{
            
            width: i === count - 1 ? width : '100%',
            height,
            
            marginBottom: i < count - 1 ? '0.5rem' : 0,
            ...style,
          }}
        />
      ))}
    </>
  );
}

export default LoadingSkeleton;
