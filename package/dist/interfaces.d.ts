export interface ClientMessageLoad {
    action: "load";
    modelUrl: string;
}
export interface ClientMessageTerminate {
    action: "terminate";
}
export interface ClientMessageRecognizerSet {
    action: "set";
    recognizerId: string;
    key: "words";
    value: boolean;
}
export interface ClientMessageGenericSet {
    action: "set";
    key: "logLevel";
    value: number;
}
export declare type ClientMessageSet = ClientMessageRecognizerSet | ClientMessageGenericSet;
export interface ClientMessageAudioChunk {
    action: "audioChunk";
    recognizerId: string;
    data: Float32Array;
    sampleRate: number;
}
export interface ClientMessageCreateRecognizer {
    action: "create";
    recognizerId: string;
    sampleRate: number;
    grammar?: string;
}
export interface ClientMessageRetrieveFinalResult {
    action: "retrieveFinalResult";
    recognizerId: string;
}
export interface ClientMessageRemoveRecognizer {
    action: "remove";
    recognizerId: string;
}
export declare type ClientMessage = ClientMessageTerminate | ClientMessageLoad | ClientMessageCreateRecognizer | ClientMessageAudioChunk | ClientMessageSet | ClientMessageRetrieveFinalResult | ClientMessageRemoveRecognizer;
export declare namespace ClientMessage {
    function isTerminateMessage(message: ClientMessage): message is ClientMessageTerminate;
    function isLoadMessage(message: ClientMessage): message is ClientMessageLoad;
    function isSetMessage(message: ClientMessage): message is ClientMessageSet;
    function isAudioChunkMessage(message: ClientMessage): message is ClientMessageAudioChunk;
    function isRecognizerCreateMessage(message: ClientMessage): message is ClientMessageCreateRecognizer;
    function isRecognizerRetrieveFinalResultMessage(message: ClientMessage): message is ClientMessageRetrieveFinalResult;
    function isRecognizerRemoveMessage(message: ClientMessage): message is ClientMessageRemoveRecognizer;
}
export interface ServerMessageLoadResult {
    event: "load";
    result: boolean;
}
export interface ServerMessageError {
    event: "error";
    recognizerId?: string;
    error: string;
}
export interface ServerMessageResult {
    event: "result";
    recognizerId: string;
    result: {
        result: Array<{
            conf: number;
            start: number;
            end: number;
            word: string;
        }>;
        text: string;
    };
}
export interface ServerMessagePartialResult {
    event: "partialresult";
    recognizerId: string;
    result: {
        partial: string;
    };
}
export declare type ModelMessage = ServerMessageLoadResult | ServerMessageError;
export declare namespace ModelMessage {
    function isLoadResult(message: any): message is ServerMessageLoadResult;
}
export declare type RecognizerMessage = ServerMessagePartialResult | ServerMessageResult | ServerMessageError;
export declare type RecognizerEvent = RecognizerMessage["event"];
export declare type ServerMessage = ModelMessage | RecognizerMessage;
export declare namespace ServerMessage {
    function isRecognizerMessage(message: ServerMessage): message is RecognizerMessage;
    function isResult(message: any): message is ServerMessageResult;
    function isPartialResult(message: any): message is ServerMessagePartialResult;
}
