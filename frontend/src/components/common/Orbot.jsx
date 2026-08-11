import React from 'react';

const Orbot = ({ size = 120, state = 'floating', className = '' }) => {
  // state can be 'floating', 'searching', 'empty-library', 'chatting'

  return (
    <div className={`orbot-container orbot-${state} ${className}`} style={{ width: size, height: size, position: 'relative' }}>
      <svg viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Orbit Rings (background) */}
        {(state === 'floating' || state === 'searching') && (
           <g stroke="#E5E5E5" strokeWidth="1" opacity="0.6">
             <ellipse cx="50" cy="50" rx="40" ry="15" transform="rotate(20 50 50)" />
             <ellipse cx="50" cy="50" rx="40" ry="15" transform="rotate(-40 50 50)" />
           </g>
        )}
        
        {/* Head */}
        <rect x="35" y="25" width="30" height="24" rx="12" fill="#FFFFFF" stroke="#333333" strokeWidth="2" />
        {/* Face Screen */}
        <rect x="38" y="28" width="24" height="14" rx="7" fill="#111111" />
        
        {/* Eyes based on state */}
        {state === 'empty-library' ? (
          <g fill="#FFFFFF">
             <rect x="42" y="32" width="6" height="2" rx="1" />
             <rect x="52" y="32" width="6" height="2" rx="1" />
          </g>
        ) : state === 'searching' ? (
           <g fill="#FFFFFF">
             <circle cx="45" cy="35" r="2.5" />
             <circle cx="55" cy="35" r="1.5" />
          </g>
        ) : (
          <g fill="#FFFFFF">
             <circle cx="45" cy="35" r="2.5" />
             <circle cx="55" cy="35" r="2.5" />
          </g>
        )}

        {/* Antenna */}
        <line x1="50" y1="25" x2="50" y2="15" stroke="#333333" strokeWidth="2" />
        <circle cx="50" cy="15" r="3" fill="#FFFFFF" stroke="#333333" strokeWidth="2" />
        
        {/* Body */}
        <path d="M40 55 C40 45, 60 45, 60 55 L58 70 C58 75, 42 75, 42 70 Z" fill="#FFFFFF" stroke="#333333" strokeWidth="2" />
        
        {/* Details */}
        <circle cx="50" cy="62" r="4" fill="#E5E5E5" stroke="#333333" strokeWidth="1.5" />
        
        {/* Arms */}
        {state === 'empty-library' ? (
           <g stroke="#333333" strokeWidth="2" fill="none">
             {/* Holding doc */}
             <path d="M40 58 C32 60, 32 68, 42 68" />
             <path d="M60 58 C68 60, 68 68, 58 68" />
             <rect x="42" y="62" width="16" height="20" fill="#FFFFFF" strokeWidth="1.5" rx="1" transform="rotate(-10 50 70)"/>
             <line x1="45" y1="67" x2="55" y2="67" strokeWidth="1" transform="rotate(-10 50 70)"/>
             <line x1="45" y1="71" x2="53" y2="71" strokeWidth="1" transform="rotate(-10 50 70)"/>
           </g>
        ) : state === 'searching' ? (
           <g stroke="#333333" strokeWidth="2" fill="none">
             <path d="M40 55 C30 50, 25 55, 30 65" />
             <path d="M60 55 C70 50, 75 55, 70 65" />
             {/* Magnifying glass */}
             <circle cx="70" cy="65" r="5" strokeWidth="1.5" fill="#FFFFFF" />
             <line x1="66" y1="69" x2="62" y2="73" strokeWidth="1.5" />
           </g>
        ) : state === 'chatting' ? (
           <g stroke="#333333" strokeWidth="2" fill="none">
             <path d="M40 58 C32 60, 30 70, 35 75" />
             <path d="M60 58 C68 50, 80 50, 85 45" /> {/* Raising hand */}
           </g>
        ) : (
           <g stroke="#333333" strokeWidth="2" fill="none">
             <path d="M40 58 C32 60, 30 70, 35 75" />
             <path d="M60 58 C68 60, 70 70, 65 75" />
           </g>
        )}
      </svg>
      
      {/* Floating animation keyframes */}
      <style>
        {`
          @keyframes orbot-float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
            100% { transform: translateY(0px); }
          }
          .orbot-floating svg {
            animation: orbot-float 4s ease-in-out infinite;
          }
        `}
      </style>
    </div>
  );
};

export default Orbot;
