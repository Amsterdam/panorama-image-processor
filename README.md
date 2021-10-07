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


## Getting started

### Credentials

Credentials to work with the queue can be retrieved from the azure dashboard.
Visit: [https://portal.azure.com/#home]
Go to _storage accounts -> panodpanoz3mww6rxd6bjk -> access keys_

Copy connection string

**Note:** Do not rotate keys, or colleagues will be locked out. 

Set environment

```shell
export AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol={MORE KEY GIBBERISH HERE}
```

Run queue tool
```shell
queue --help
```

### Prepare

Run prepare to make MSGFILE. Source for this message file is a container (a storage folder) on azure.


```shell
queue prepare msgfile.msg 2018 
```

Store the message file and the missing files on azure in the "queued" container.


### Fill queue

Process images. This runs on a Kubernetes cluster.
```shell
queue fill msgfile.msg
```

Use `queue status` to monitor the status of the queue. 
Messages which get stuck because they cannot be processed can be removed by `queue flush`.


### Transfer results to CloudVPS




# Kubernetes infrastructure.

The kubernetes cluster used to run the containers in is: `ont-blue aks`.

When code for the panorama container is changed, a new container has to be build and deployed manually.
Kubernetes does not automatically pick up the new container.

