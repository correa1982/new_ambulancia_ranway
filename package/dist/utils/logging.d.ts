export declare class Logger {
    private logLevel;
    constructor(logLevel?: number);
    getLogLevel(): number;
    setLogLevel(level: number): void;
    error(message: string): void;
    warn(message: string): void;
    info(message: string): void;
    verbose(message: string): void;
    debug(message: string): void;
}
