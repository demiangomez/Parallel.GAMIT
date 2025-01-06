const useDebounce = (func: any, limit: number) => {
    let inThrottle: boolean;
    let lastResult: any;
  
    return async function (this: any, ...args : any[]) {
      if (!inThrottle) {
        inThrottle = true;
        
        // Ejecutar la función y guardar el resultado
        lastResult = await func.apply(this, args);
        
        // Resetear el throttle después del límite
        setTimeout(() => {
          inThrottle = false;
        }, limit);
      }
      
      // Retornar el último resultado
      return lastResult;
    };
  };

export default useDebounce;
  
