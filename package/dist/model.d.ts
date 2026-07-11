import { ModelMessage, RecognizerEvent, RecognizerMessage } from "./interfaces";
export declare class Model extends EventTarget {
    private modelUrl;
    private worker;
    private _ready;
    private messagePort;
    private logger;
    private recognizers;
    constructor(modelUrl: string, logLevel?: number);
    private initialize;
    private postMessage;
    private handleMessage;
    on(event: ModelMessage["event"], listener: (message: ModelMessage) => void): void;
    registerPort(port: MessagePort): void;
    private forwardMessage;
    get ready(): boolean;
    terminate(): void;
    setLogLevel(level: number): void;
    registerRecognizer(recognizer: KaldiRecognizer): void;
    unregisterRecognizer(recognizerId: string): void;
    /**
     * KaldiRecognizer anonymous class
     */
    get KaldiRecognizer(): {
        new (sampleRate: number, grammar?: string): {
            id: string;
            on(event: RecognizerEvent, listener: (message: RecognizerMessage) => void): void;
            setWords(words: boolean): void;
            acceptWaveform(buffer: AudioBuffer): void;
            acceptWaveformFloat(buffer: Float32Array, sampleRate: number): void;
            retrieveFinalResult(): void;
            remove(): void;
            addEventListener(type: string, callback: EventListenerOrEventListenerObject | null, options?: boolean | AddEventListenerOptions | undefined): void;
            dispatchEvent(event: Event): boolean;
            removeEventListener(type: string, callback: EventListenerOrEventListenerObject | null, options?: boolean | EventListenerOptions | undefined): void;
        };
    };
}
export declare type KaldiRecognizer = InstanceType<Model["KaldiRecognizer"]>;
export declare function createModel(modelUrl: string, logLevel?: number): Promise<Model>;
