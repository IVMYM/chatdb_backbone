import React, { createContext, useState, useEffect } from 'react';

export const UserContext = createContext<any>(null);

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<any>(null);

  useEffect(()=>{
    const token = localStorage.getItem('token');
    if(token){
      // you can fetch /api/auth/me here to validate
      setUser({ username: 'demo' });
    }
  },[]);

  return <UserContext.Provider value={{user, setUser}}>{children}</UserContext.Provider>;
}
