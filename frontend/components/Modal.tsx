import React from 'react';

export default function Modal({open, onClose, title, children}:{open:boolean,onClose:()=>void,title?:string,children:any}) {
  if(!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black opacity-30" onClick={onClose}></div>
      <div className="bg-white rounded shadow p-6 z-10 w-full max-w-xl">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button onClick={onClose} className="text-gray-500">Close</button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
