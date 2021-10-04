# Panorama Image Processor

The new panorama image processor container using the algoritm developed by CTO.

## Tools

Tools are available in the virtualenv with the queue command.
These tools are dedicated to Azure for now.
Intention for the queue tools is to:
 *. prepare missions to a message file
 *. fill the processing queue with a message file
 *. Calc the processing speed for the current queued messages
 *. Get the status for a processed compared to a message file
 *. Flush (clear) a complete queue
 *. Peek for a couple of messages in the queue